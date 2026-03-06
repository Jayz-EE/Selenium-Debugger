#!/usr/bin/env python3
"""
RMS Selenium Test Suite v1.0 - Comprehensive automated testing for RMS.
Cross-platform compatible. Exception-safe: logs errors without stopping.

Usage:
    python rms_selenium_test.py --url http://localhost:8000
    python rms_selenium_test.py --url http://localhost:8000 --headless --roles admin,teacher
    python rms_selenium_test.py --url http://localhost:8000 --skip-destructive
"""

import os, sys, json, time, random, string, logging, argparse, platform, traceback, re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
from urllib.parse import urljoin, urlparse, quote
import warnings, requests
warnings.filterwarnings("ignore")

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException, ElementClickInterceptedException,
        StaleElementReferenceException, WebDriverException, InvalidSessionIdException,
        ElementNotInteractableException, NoAlertPresentException, UnexpectedAlertPresentException
    )
except ImportError:
    print("[!] Selenium not installed. Run: pip install selenium webdriver-manager")
    sys.exit(1)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    HAS_WDM = True
except ImportError:
    HAS_WDM = False

# ============================================================
# DATA CLASSES
# ============================================================
class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class TestStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    WARNING = "WARNING"

@dataclass
class Finding:
    category: str; severity: str; title: str; detail: str
    endpoint: str = ""; role: str = ""; timestamp: str = ""
    def __post_init__(self):
        if not self.timestamp: self.timestamp = datetime.now().isoformat()

@dataclass
class TestResult:
    test_name: str; status: str; duration: float = 0.0; message: str = ""
    endpoint: str = ""; role: str = ""; findings: List[Finding] = field(default_factory=list)
    timestamp: str = ""
    def __post_init__(self):
        if not self.timestamp: self.timestamp = datetime.now().isoformat()

# ============================================================
# MOCK DATABASE
# ============================================================
class MockDatabase:
    def __init__(self):
        self.students, self.teachers, self.courses = [], [], []
        self.subjects, self.schedules, self.finances = [], [], []
        self.users = {}
        self._build()

    def _build(self):
        for i, (c, n) in enumerate([("BSIT","BS Information Technology"),("BSCS","BS Computer Science"),
            ("BSA","BS Accountancy"),("BSBA","BS Business Admin"),("BSN","BS Nursing"),
            ("BSED","BS Secondary Ed"),("BEED","Bachelor Elementary Ed"),("BSCRIM","BS Criminology")], 1):
            self.courses.append({"id":i,"code":c,"name":n})
        for i, n in enumerate(["Intro Computing","Data Structures","Web Dev","Database Mgmt",
            "Software Eng","Network Admin","OS","Calculus I","English","PH History",
            "Chemistry","Physics I","Statistics","Discrete Math","Ethics"], 1):
            self.subjects.append({"id":i,"code":f"SUBJ-{i:03d}","name":n,"units":random.choice([2,3,5])})
        fnames = ["Juan","Maria","Jose","Ana","Pedro","Rosa","Carlos","Elena","Miguel","Sofia",
                  "Antonio","Luisa","Rafael","Carmen","Diego","Isabella","Fernando","Teresa","Manuel","Patricia"]
        lnames = ["Santos","Reyes","Cruz","Bautista","Garcia","Mendoza","Torres","Flores","Rivera","Ramos"]
        for i in range(20):
            fn, ln = fnames[i%len(fnames)], lnames[i%len(lnames)]
            self.students.append({"id":i+1,"student_id":f"2024-{random.randint(10000,99999)}",
                "first_name":fn,"last_name":ln,"email":f"{fn.lower()}.{ln.lower()}@test.edu.ph",
                "course_id":random.randint(1,8),"year_level":random.randint(1,4)})
        for i in range(10):
            self.teachers.append({"id":i+1,"name":f"Prof. Teacher{i+1}","email":f"teacher{i+1}@test.edu.ph"})
        days = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
        times = ["07:00-08:30","08:30-10:00","10:00-11:30","13:00-14:30"]
        for i in range(15):
            self.schedules.append({"id":i+1,"subject_id":random.randint(1,15),
                "teacher_id":random.randint(1,10),"day":random.choice(days),"time":random.choice(times)})
        for s in self.students:
            t = round(random.uniform(15000,50000),2); p = round(random.uniform(0,t),2)
            self.finances.append({"id":s["id"],"student_id":s["id"],"tuition":t,"paid":p,"balance":round(t-p,2)})
        for role in ["admin","admission","pre_admission","academic_director","program_head",
                     "registrar","teacher","cashier","finance","guidance","clinic","it_staff","scholarship","librarian"]:
            self.users[role] = {"username":f"test_{role}","password":f"TestPass_{role}_2024!","role":role}

    def get_test_data(self, path):
        p = path.lower()
        if "student" in p and self.students: return random.choice(self.students)
        if "teacher" in p and self.teachers: return random.choice(self.teachers)
        if "course" in p and self.courses: return random.choice(self.courses)
        if "finance" in p and self.finances: return random.choice(self.finances)
        return {}

    def export(self): return {"students":self.students,"teachers":self.teachers,"courses":self.courses,
                              "subjects":self.subjects,"schedules":self.schedules,"finances":self.finances,"users":self.users}

# ============================================================
# SMART NAVIGATOR
# ============================================================
class SmartNavigator:
    def __init__(self, driver, logger):
        self.driver = driver
        self.logger = logger
        self.page_load_count = 0

    def navigate(self, url, wait=True):
        try:
            self.logger.debug(f"NAV -> {url}")
            self.driver.get(url); self.page_load_count += 1
            if wait: self._wait_load()
            self._dismiss_alerts()
            return True
        except UnexpectedAlertPresentException:
            self._dismiss_alerts(); return True
        except TimeoutException:
            return True
        except Exception as e:
            self.logger.error(f"Nav failed: {url} - {e}"); return False

    def _wait_load(self, t=10):
        try:
            WebDriverWait(self.driver, t).until(lambda d: d.execute_script("return document.readyState")=="complete")
            try:
                if self.driver.execute_script("return typeof jQuery!=='undefined'"):
                    WebDriverWait(self.driver, 3).until(lambda d: d.execute_script("return jQuery.active===0"))
            except: pass
            for sel in [".loading",".spinner","#loading",".preloader"]:
                try: WebDriverWait(self.driver, 2).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, sel)))
                except: pass
        except: pass

    def _dismiss_alerts(self):
        try: a = self.driver.switch_to.alert; self.logger.info(f"Alert: {a.text[:60]}"); a.accept()
        except: pass

    def find_el(self, by, val, t=10):
        try: return WebDriverWait(self.driver, t).until(EC.presence_of_element_located((by, val)))
        except: return None

    def find_els(self, by, val, t=3):
        try:
            WebDriverWait(self.driver, t).until(EC.presence_of_element_located((by, val)))
            return self.driver.find_elements(by, val)
        except: return []

    def click_safe(self, el, retry=3):
        for _ in range(retry):
            try:
                self.logger.debug("CLICK")
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                ActionChains(self.driver).move_to_element(el).pause(0.1).click().perform()
                return True
            except ElementClickInterceptedException:
                try:
                    self.driver.execute_script("arguments[0].click();", el); return True
                except StaleElementReferenceException: time.sleep(0.5)
                except:
                    try: self.driver.execute_script("arguments[0].click();", el); return True
                    except: pass
        return False

    def fill_input(self, el, val):
        try:
            self.logger.debug(f"FILL len={len(str(val))}")
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            el.clear(); time.sleep(0.1); el.send_keys(val); return True
        except Exception as e:
            self.logger.debug(f"Fill failed: {e}"); return False

    def get_csrf(self):
        for fn in [
            lambda: self.driver.find_element(By.CSS_SELECTOR,"input[name='csrfmiddlewaretoken']").get_attribute("value"),
            lambda: self.driver.get_cookie("csrftoken")["value"] if self.driver.get_cookie("csrftoken") else None,
            lambda: self.driver.execute_script("return document.querySelector('[name=csrfmiddlewaretoken]')?.value||document.cookie.match(/csrftoken=([^;]+)/)?.[1]"),
        ]:
            try:
                v = fn()
                if v: return v
            except: pass
        return None

    def detect_elements(self):
        r = {"forms":[],"links":[],"buttons":[],"inputs":[],"tables":[],"modals":[],"tabs":[],"selects":[],"nav_items":[]}
        try:
            r["forms"] = self.find_els(By.TAG_NAME,"form")
            r["links"] = self.find_els(By.TAG_NAME,"a")
            r["buttons"] = self.find_els(By.TAG_NAME,"button") + self.find_els(By.CSS_SELECTOR,"input[type='submit'],[role='button']")
            r["inputs"] = self.find_els(By.TAG_NAME,"input") + self.find_els(By.TAG_NAME,"textarea")
            r["tables"] = self.find_els(By.TAG_NAME,"table")
            r["modals"] = self.find_els(By.CSS_SELECTOR,".modal")
            r["tabs"] = self.find_els(By.CSS_SELECTOR,".nav-tabs .nav-link,[data-bs-toggle='tab'],[data-toggle='tab']")
            r["selects"] = self.find_els(By.TAG_NAME,"select") + self.find_els(By.CSS_SELECTOR,".select2-container")
            r["nav_items"] = self.find_els(By.CSS_SELECTOR,".sidebar a,.side-nav a,nav a,.navbar a,.nav-link")
        except: pass
        return r

    def interact_modal(self, trigger):
        res = {"opened":False,"has_form":False,"fields":[],"title":""}
        try:
            self.click_safe(trigger); time.sleep(1)
            m = self.find_el(By.CSS_SELECTOR,".modal.show,.modal.in,.modal[style*='display: block']",5)
            if m:
                res["opened"] = True
                t = m.find_elements(By.CSS_SELECTOR,".modal-title,.modal-header h5")
                if t: res["title"] = t[0].text
                f = m.find_elements(By.TAG_NAME,"form")
                if f:
                    res["has_form"] = True
                    res["fields"] = [{"name":i.get_attribute("name"),"type":i.get_attribute("type") or "text"}
                                     for i in f[0].find_elements(By.CSS_SELECTOR,"input,select,textarea") if i.get_attribute("name")]
                c = m.find_elements(By.CSS_SELECTOR,".btn-close,[data-bs-dismiss='modal'],[data-dismiss='modal'],.close")
                if c: self.click_safe(c[0])
                else: self.driver.execute_script("document.querySelectorAll('.modal').forEach(m=>m.style.display='none');document.querySelectorAll('.modal-backdrop').forEach(b=>b.remove());")
                time.sleep(0.3)
        except: pass
        return res

    def get_page_info(self):
        info = {"url":self.driver.current_url,"title":self.driver.title,"errors":[],"console_errors":[]}
        try:
            for sel in [".alert-danger",".error",".errors",".errorlist",".text-danger",".invalid-feedback"]:
                for el in self.find_els(By.CSS_SELECTOR, sel, 1):
                    t = el.text.strip()
                    if t: info["errors"].append(t[:200])
            try:
                for entry in self.driver.get_log("browser"):
                    if entry.get("level") in ("SEVERE","ERROR"):
                        info["console_errors"].append(entry.get("message","")[:200])
            except: pass
        except: pass
        return info

    def screenshot(self, name, out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
            p = os.path.join(out_dir, f"{re.sub(r'[^w.-]','_',name)[:60]}_{int(time.time())}.png")
            self.driver.save_screenshot(p); return p
        except: return ""

# ============================================================
# RMS TEST SUITE
# ============================================================
class RMSTestSuite:
    VERSION = "1.0"
    MAX_DISCOVERED_PAGES = 150

    def __init__(self, base_url, config_path=None, headless=False, browser="chrome",
                 roles_filter=None, skip_destructive=False, delay=0.5, output_dir=None,
                 verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self.browser_name = browser.lower()
        self.roles_filter = roles_filter
        self.skip_destructive = skip_destructive
        self.delay = delay
        self.output_dir = output_dir or os.path.join(os.getcwd(), "rms_test_results")
        self.screenshots_dir = os.path.join(self.output_dir, "screenshots")
        self.config = self._load_config(config_path)
        self.mock_db = MockDatabase()
        self.verbose = verbose
        self.generated_role_credentials: Dict[str, Dict] = {}
        self.results: List[TestResult] = []
        self.findings: List[Finding] = []
        self.tested_endpoints: Dict[str, Dict] = {}
        self.discovered_pages: List[str] = []
        self.start_time = self.end_time = None
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({"User-Agent": "RMS-TestSuite/1.0"})
        self.logger = self._setup_logger()
        self.driver = None
        self.nav = None

    def _load_config(self, path=None):
        for p in [path, os.path.join(os.path.dirname(os.path.abspath(__file__)), "rms_test_config.json")]:
            if p and os.path.exists(p):
                with open(p) as f: return json.load(f)
        return {"roles": [], "api_endpoints": {}, "web_endpoints": {}, "authentication": {}, "test_scenarios": {}}

    def _setup_logger(self):
        os.makedirs(self.output_dir, exist_ok=True)
        logger = logging.getLogger("RMSTest")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        fh = logging.FileHandler(os.path.join(self.output_dir, "test_run.log"), mode="w")
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        fmt = logging.Formatter("[%(asctime)s] %(levelname)-7s %(message)s", "%H:%M:%S")
        fh.setFormatter(fmt); ch.setFormatter(fmt)
        logger.addHandler(fh); logger.addHandler(ch)
        return logger

    def _init_driver(self):
        self.logger.info(f"Initializing {self.browser_name} (headless={self.headless}) on {platform.system()}")
        for br in ([self.browser_name] + [b for b in ["chrome","firefox","edge"] if b != self.browser_name]):
            try:
                d = self._create_driver(br)
                if d:
                    self.browser_name = br; d.set_page_load_timeout(30)
                    d.implicitly_wait(5); d.set_window_size(1920, 1080)
                    self.driver = d; self.nav = SmartNavigator(d, self.logger)
                    self.logger.info(f"Browser ready: {br}"); return
            except Exception as e:
                self.logger.warning(f"{br} failed: {e}")
        raise RuntimeError("No compatible browser found. Install Chrome, Firefox, or Edge.")

    def _create_driver(self, browser):
        if browser == "chrome":
            opts = ChromeOptions()
            if self.headless: opts.add_argument("--headless=new")
            for a in ["--no-sandbox","--disable-dev-shm-usage","--disable-gpu",
                       "--window-size=1920,1080","--ignore-certificate-errors","--log-level=3"]:
                opts.add_argument(a)
            opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})
            if HAS_WDM: return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)
            return webdriver.Chrome(options=opts)
        elif browser == "firefox":
            opts = FirefoxOptions()
            if self.headless: opts.add_argument("--headless")
            opts.accept_insecure_certs = True
            if HAS_WDM: return webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=opts)
            return webdriver.Firefox(options=opts)
        elif browser == "edge":
            opts = EdgeOptions()
            if self.headless: opts.add_argument("--headless=new")
            for a in ["--no-sandbox","--ignore-certificate-errors"]: opts.add_argument(a)
            if HAS_WDM: return webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=opts)
            return webdriver.Edge(options=opts)
        return None

    def _throttle(self):
        if self.delay > 0: time.sleep(self.delay)

    def _add_finding(self, cat, sev, title, detail, endpoint="", role=""):
        self.findings.append(Finding(cat, sev, title, detail, endpoint, role))
        lvl = {"CRITICAL":50,"HIGH":40,"MEDIUM":30,"LOW":20,"INFO":10}.get(sev, 20)
        self.logger.log(lvl, f"[{sev}] {cat}: {title}")

    def _add_result(self, name, status, msg="", endpoint="", role="", findings=None, duration=0.0):
        self.results.append(TestResult(name, status, duration, msg, endpoint, role, findings or []))

    def _safe_exec(self, name, func, *args, **kwargs):
        start = time.time()
        try:
            return func(*args, **kwargs)
        except (InvalidSessionIdException, WebDriverException) as e:
            if "invalid session" in str(e).lower():
                self.logger.error(f"Session lost in {name}. Restarting browser...")
                try: self._init_driver()
                except: self.logger.critical("Browser restart failed")
            self._add_result(name, "ERROR", str(e)[:200], duration=time.time()-start)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            self.logger.error(f"Error in {name}: {e}")
            self.logger.debug(traceback.format_exc())
            self._add_result(name, "ERROR", str(e)[:300], duration=time.time()-start)
        return None

    def _role_login_credentials(self, role_cfg):
        role_name = role_cfg.get("name", role_cfg.get("slug", "unknown"))
        role_slug = role_cfg.get("slug", role_name.lower().replace(" ", "_"))
        cfg_creds = role_cfg.get("credentials", {}) or {}
        source = role_cfg.get("credential_source", "manual" if role_slug == "admin" else "generated")
        if role_slug == "admin" or source == "manual":
            return cfg_creds
        return self.generated_role_credentials.get(role_slug) or self.mock_db.users.get(role_slug, {})

    def _admin_role_cfg(self):
        for role_cfg in self.config.get("roles", []):
            if role_cfg.get("slug", "").lower() == "admin":
                return role_cfg
        return None

    def _prepare_generated_role_credentials(self):
        self.generated_role_credentials = {}
        for role_cfg in self.config.get("roles", []):
            role_name = role_cfg.get("name", role_cfg.get("slug", "unknown"))
            role_slug = role_cfg.get("slug", role_name.lower().replace(" ", "_"))
            if role_slug == "admin":
                continue
            mock_creds = dict(self.mock_db.users.get(role_slug, {}))
            if not mock_creds:
                mock_creds = {
                    "username": f"test_{role_slug}",
                    "password": f"TestPass_{role_slug}_2024!",
                    "role": role_slug,
                }
            mock_creds.setdefault("email", f"{role_slug}@test.edu.ph")
            self.generated_role_credentials[role_slug] = mock_creds

    def provision_role_accounts(self):
        start = time.time()
        self._prepare_generated_role_credentials()
        admin_cfg = self._admin_role_cfg()
        if not admin_cfg:
            self._add_result("Provision Role Accounts", "SKIPPED", "Admin role not configured", duration=time.time()-start)
            return False
        admin_creds = self._role_login_credentials(admin_cfg)
        if not admin_creds.get("username") or not admin_creds.get("password"):
            self._add_result("Provision Role Accounts", "SKIPPED", "Admin credentials required", role="Admin", duration=time.time()-start)
            return False
        if not self.test_login_with_role(admin_cfg):
            self._add_result("Provision Role Accounts", "WARNING", "Admin login failed; using generated credentials without UI provisioning", role="Admin", duration=time.time()-start)
            return False
        created = []
        for role_cfg in self.config.get("roles", []):
            role_name = role_cfg.get("name", role_cfg.get("slug", "unknown"))
            role_slug = role_cfg.get("slug", role_name.lower().replace(" ", "_"))
            if role_slug == "admin":
                continue
            creds = self.generated_role_credentials.get(role_slug, {})
            if self._attempt_create_role_user(role_cfg, creds):
                created.append(role_slug)
            self._throttle()
        self.test_logout()
        status = "PASSED" if created else "WARNING"
        msg = f"Prepared {len(self.generated_role_credentials)} generated roles; UI-created {len(created)}"
        self._add_result("Provision Role Accounts", status, msg, role="Admin", duration=time.time()-start)
        return True

    def _attempt_create_role_user(self, role_cfg, creds):
        role_name = role_cfg.get("name", role_cfg.get("slug", "unknown"))
        candidate_paths = [
            "/administrator/users/create/",
            "/administrator/users/add/",
            "/administrator/manage_users/",
            "/admin/auth/user/add/",
            "/admin/users/add/",
        ]
        for path in candidate_paths:
            try:
                url = urljoin(self.base_url, path)
                self.nav.navigate(url)
                time.sleep(0.7)
                forms = self.nav.find_els(By.TAG_NAME, "form", 2)
                if not forms:
                    continue
                if self._fill_role_creation_form(role_cfg, creds):
                    self._add_finding("Setup", "INFO", f"Generated account prepared for {role_name}", f"Username: {creds.get('username','')}", endpoint=path, role=role_name)
                    return True
            except Exception:
                pass
        return False

    def _fill_role_creation_form(self, role_cfg, creds):
        username = creds.get("username", "")
        password = creds.get("password", "")
        email = creds.get("email", "")
        role_name = role_cfg.get("name", role_cfg.get("slug", "unknown"))
        if not username or not password:
            return False
        field_specs = [
            (["input[name='username']", "input[id*='username']"], username),
            (["input[name='email']", "input[type='email']", "input[id*='email']"], email),
            (["input[name='password']", "input[type='password']", "input[id*='password1']"], password),
            (["input[name='password1']", "input[id*='password1']"], password),
            (["input[name='password2']", "input[id*='password2']", "input[name='confirm_password']"], password),
            (["input[name='first_name']", "input[id*='first_name']"], role_name.split()[0]),
            (["input[name='last_name']", "input[id*='last_name']"], "Test"),
        ]
        touched = False
        for selectors, value in field_specs:
            for selector in selectors:
                el = self.nav.find_el(By.CSS_SELECTOR, selector, 1)
                if el:
                    self.nav.fill_input(el, value)
                    touched = True
                    break
        for selector in ["select[name='role']", "select[id*='role']", "select[name='user_type']", "select[id*='user_type']"]:
            el = self.nav.find_el(By.CSS_SELECTOR, selector, 1)
            if el:
                try:
                    Select(el).select_by_visible_text(role_name)
                except Exception:
                    try:
                        Select(el).select_by_value(role_cfg.get("slug", ""))
                    except Exception:
                        pass
                touched = True
                break
        if not touched:
            return False
        submit = (self.nav.find_el(By.CSS_SELECTOR, "button[type='submit']", 1) or
                  self.nav.find_el(By.CSS_SELECTOR, "input[type='submit']", 1) or
                  self.nav.find_el(By.CSS_SELECTOR, "form button", 1))
        if submit and not self.skip_destructive:
            try:
                self.nav.click_safe(submit)
                time.sleep(1)
            except Exception:
                pass
        return True

    # ==================== AUTHENTICATION ====================
    def test_login_page(self):
        self.logger.info("=" * 60)
        self.logger.info("TESTING: Login Page")
        self.logger.info("=" * 60)
        start = time.time()
        self.nav.navigate(self.base_url)
        elements = self.nav.detect_elements()
        user_f = (self.nav.find_el(By.CSS_SELECTOR,"input[name='username']",3) or
                  self.nav.find_el(By.CSS_SELECTOR,"input[name='email']",2) or
                  self.nav.find_el(By.CSS_SELECTOR,"input[type='text']",2))
        pass_f = self.nav.find_el(By.CSS_SELECTOR,"input[type='password']",3)
        findings = []
        if not elements["forms"]:
            findings.append(Finding("Functionality","MEDIUM","No login form found","Page may not be login page",endpoint="/"))
        if not pass_f:
            findings.append(Finding("Functionality","MEDIUM","No password field found","Missing password input",endpoint="/"))
        if not self.base_url.startswith("https"):
            findings.append(Finding("Security","HIGH","Login page not using HTTPS",f"URL: {self.base_url}",endpoint="/"))
        if pass_f:
            ac = pass_f.get_attribute("autocomplete")
            if ac not in ("off","new-password","current-password"):
                findings.append(Finding("Security","LOW","Password autocomplete not restricted",f"autocomplete='{ac}'",endpoint="/"))
        status = "PASSED" if elements["forms"] and pass_f else "WARNING"
        self._add_result("Login Page Load", status, f"Forms:{len(elements['forms'])} Inputs:{len(elements['inputs'])}",
                         endpoint="/", findings=findings, duration=time.time()-start)
        for f in findings: self.findings.append(f)

    def test_login_with_role(self, role_cfg) -> bool:
        role_name = role_cfg.get("name", role_cfg.get("slug","unknown"))
        creds = self._role_login_credentials(role_cfg)
        username, password = creds.get("username",""), creds.get("password","")
        if not username or not password:
            self.logger.info(f"  Skipping login for {role_name} - no credentials")
            self._add_result(f"Login-{role_name}", "SKIPPED", "No credentials", role=role_name)
            return False
        self.logger.info(f"  Attempting login as {role_name}...")
        start = time.time()
        try:
            self.nav.navigate(self.base_url); time.sleep(0.5)
            uf = (self.nav.find_el(By.CSS_SELECTOR,"input[name='username']",3) or
                  self.nav.find_el(By.CSS_SELECTOR,"input[name='email']",2) or
                  self.nav.find_el(By.CSS_SELECTOR,"input[type='text']",2))
            pf = self.nav.find_el(By.CSS_SELECTOR,"input[type='password']",3)
            if not uf or not pf:
                self._add_result(f"Login-{role_name}","ERROR","Login fields not found",role=role_name,duration=time.time()-start)
                return False
            self.nav.fill_input(uf, username); self.nav.fill_input(pf, password)
            sub = (self.nav.find_el(By.CSS_SELECTOR,"button[type='submit']",2) or
                   self.nav.find_el(By.CSS_SELECTOR,"input[type='submit']",2) or
                   self.nav.find_el(By.CSS_SELECTOR,"form button",2))
            if sub: self.nav.click_safe(sub)
            else: pf.send_keys(Keys.RETURN)
            time.sleep(2); self.nav._wait_load()
            cur = self.driver.current_url; info = self.nav.get_page_info()
            ok = (cur != self.base_url+"/" and cur != self.base_url and "login" not in cur.lower())
            if info["errors"]: ok = False
            if ok:
                self.logger.info(f"  Login OK for {role_name} -> {cur}")
                self._add_result(f"Login-{role_name}","PASSED",f"Redirect: {cur}",role=role_name,duration=time.time()-start)
                for c in self.driver.get_cookies(): self.session.cookies.set(c["name"], c["value"])
            else:
                self.logger.info(f"  Login FAILED for {role_name}")
                self._add_result(f"Login-{role_name}","FAILED",f"At: {cur} Errors: {info['errors'][:2]}",role=role_name,duration=time.time()-start)
            return ok
        except Exception as e:
            self._add_result(f"Login-{role_name}","ERROR",str(e)[:200],role=role_name,duration=time.time()-start)
            return False

    def test_logout(self):
        start = time.time()
        try:
            for sel in ["a[href*='logout']","a[href='/logout/']","#logout",".logout"]:
                el = self.nav.find_el(By.CSS_SELECTOR, sel, 2)
                if el: self.nav.click_safe(el); time.sleep(1); break
            else: self.nav.navigate(urljoin(self.base_url, "/logout/"))
            self.nav._wait_load()
            cur = self.driver.current_url
            out = "login" in cur.lower() or cur.rstrip("/")==self.base_url.rstrip("/")
            self._add_result("Logout","PASSED" if out else "WARNING",f"After: {cur}",duration=time.time()-start)
        except Exception as e:
            self._add_result("Logout","ERROR",str(e)[:200],duration=time.time()-start)

    def test_login_security(self):
        self.logger.info("Testing login security...")
        start = time.time()
        self.nav.navigate(self.base_url)
        uf = self.nav.find_el(By.CSS_SELECTOR,"input[name='username'],input[type='text']",3)
        pf = self.nav.find_el(By.CSS_SELECTOR,"input[type='password']",3)
        if uf and pf:
            self.nav.fill_input(uf, "nonexistent_user_xyzabc")
            self.nav.fill_input(pf, "wrongpassword123")
            sub = self.nav.find_el(By.CSS_SELECTOR,"button[type='submit'],input[type='submit']",2)
            if sub: self.nav.click_safe(sub)
            else: pf.send_keys(Keys.RETURN)
            time.sleep(1.5)
            src = self.driver.page_source.lower()
            if "username" in src and "not found" in src:
                self._add_finding("Authentication","MEDIUM","Login reveals username existence","Error distinguishes invalid username",endpoint="/")
            if "password" in src and "incorrect" in src and "username" not in src:
                self._add_finding("Authentication","MEDIUM","Login reveals wrong password for valid user","Separate error messages",endpoint="/")
        self.nav.navigate(self.base_url)
        if not self.nav.get_csrf():
            self._add_finding("Security","HIGH","No CSRF token on login form","Vulnerable to CSRF",endpoint="/")
        self._add_result("Login Security","PASSED","Checks completed",duration=time.time()-start)

    def test_password_reset(self):
        self.logger.info("Testing password reset flow...")
        start = time.time(); findings = []
        for path in ["/check_email_existence/","/verify_otp/","/reset_password/"]:
            url = urljoin(self.base_url, path)
            try:
                r = self.session.post(url, data={"email":"test@test.com"}, timeout=10)
                if r.status_code == 200:
                    findings.append(Finding("Security","HIGH",f"POST {path} accepts without CSRF",f"Status: {r.status_code}",endpoint=path))
                r2 = self.session.post(url, data={}, timeout=10)
                if r2.status_code == 200 and any(w in r2.text.lower() for w in ["traceback","exception","error"]):
                    findings.append(Finding("Security","MEDIUM",f"Error info leaked on {path}","Debug info in response",endpoint=path))
            except: pass
            self._throttle()
        for f in findings: self.findings.append(f)
        self._add_result("Password Reset","PASSED",f"{len(findings)} findings",findings=findings,duration=time.time()-start)

    # ==================== RBAC ====================
    def test_rbac(self, role_cfg, logged_in):
        role_name = role_cfg.get("name", role_cfg.get("slug","unknown"))
        role_slug = role_cfg.get("slug", role_name.lower().replace(" ","_"))
        dash = role_cfg.get("dashboard","")
        self.logger.info(f"  Testing RBAC for {role_name}")
        if dash and logged_in:
            self._safe_exec(f"RBAC-Dash-{role_name}", self._test_dashboard, role_name, dash)
        if logged_in:
            self._safe_exec(f"RBAC-Cross-{role_name}", self._test_cross_role, role_name, role_slug)

    def _test_dashboard(self, role_name, dash_path):
        url = urljoin(self.base_url, dash_path)
        self.nav.navigate(url); time.sleep(1)
        cur = self.driver.current_url
        if dash_path in cur:
            self._add_result(f"Dashboard-{role_name}","PASSED",f"Loaded: {cur}",role=role_name,endpoint=dash_path)
            els = self.nav.detect_elements()
            if not els["nav_items"] and not els["tables"] and not els["links"]:
                self._add_finding("Functionality","LOW",f"Dashboard empty for {role_name}","No content found",endpoint=dash_path,role=role_name)
        else:
            self._add_result(f"Dashboard-{role_name}","WARNING",f"Redirect: {cur}",role=role_name,endpoint=dash_path)

    def _test_cross_role(self, role_name, role_slug):
        for mod_key, mod_cfg in self.config.get("web_endpoints", {}).items():
            allowed = [r.lower().replace(" ","_") for r in mod_cfg.get("allowed_roles",[])]
            if role_slug in allowed or (role_slug == "admin"): continue
            prefix = mod_cfg.get("prefix","")
            if not prefix: continue
            url = urljoin(self.base_url, prefix + "/")
            try:
                self.nav.navigate(url); time.sleep(0.5)
                cur = self.driver.current_url
                if prefix in cur and "login" not in cur.lower():
                    self._add_finding("Authorization","HIGH",f"{role_name} can access {mod_key}",
                                      f"Accessed: {url}",endpoint=prefix,role=role_name)
            except: pass
            self._throttle()

    # ==================== WEB ENDPOINTS ====================
    def test_web_endpoints(self, role_name, role_slug):
        self.logger.info(f"  Testing web endpoints for {role_name}...")
        for mod_key, mod_cfg in self.config.get("web_endpoints", {}).items():
            allowed = [r.lower().replace(" ","_") for r in mod_cfg.get("allowed_roles",[])]
            if role_slug not in allowed and role_slug != "admin": continue
            for ep in mod_cfg.get("endpoints", []):
                method, path = ep.get("method","GET"), ep.get("path","")
                ep_type, desc = ep.get("type","web"), ep.get("description","")
                destructive = ep.get("destructive", False)
                if destructive and self.skip_destructive:
                    self._add_result(f"EP {path}","SKIPPED","Destructive",endpoint=path,role=role_name); continue
                if method == "GET":
                    self._safe_exec(f"Web-{path}", self._test_get_ep, path, ep_type, role_name, desc)
                elif method == "POST" and not destructive:
                    self._safe_exec(f"Web-{path}", self._test_post_ep, path, role_name, desc)
                self._throttle()

    def _test_get_ep(self, path, ep_type, role_name, desc):
        url = urljoin(self.base_url, path); start = time.time(); findings = []
        if ep_type == "json":
            try:
                r = self.session.get(url, timeout=10)
                self.tested_endpoints[path] = {"status":r.status_code,"type":ep_type,"role":role_name}
                if r.status_code == 200:
                    ct = r.headers.get("Content-Type","")
                    if "json" in ct:
                        try:
                            data = r.json()
                            self._analyze_json(path, data, role_name)
                        except: findings.append(Finding("Functionality","LOW",f"Invalid JSON: {path}","Parse failed",endpoint=path,role=role_name))
                    elif ep_type == "json" and "html" in ct:
                        findings.append(Finding("API","LOW",f"{path} returns HTML not JSON",f"CT: {ct}",endpoint=path,role=role_name))
                    self._check_sensitive(path, r.text[:5000], role_name)
                elif r.status_code == 500:
                    findings.append(Finding("Functionality","HIGH",f"Server error: {path}","500",endpoint=path,role=role_name))
                st = "PASSED" if r.status_code==200 else "WARNING"
                self._add_result(f"GET {path}",st,f"Status:{r.status_code} {desc}",endpoint=path,role=role_name,findings=findings,duration=time.time()-start)
            except requests.exceptions.ConnectionError:
                self._add_result(f"GET {path}","ERROR","Connection refused",endpoint=path,duration=time.time()-start)
            except Exception as e:
                self._add_result(f"GET {path}","ERROR",str(e)[:200],endpoint=path,duration=time.time()-start)
        else:
            if not self.nav.navigate(url):
                self._add_result(f"GET {path}","ERROR","Nav failed",endpoint=path,duration=time.time()-start); return
            time.sleep(0.5); info = self.nav.get_page_info(); els = self.nav.detect_elements()
            cur = self.driver.current_url
            self.tested_endpoints[path] = {"url":cur,"title":info["title"],"role":role_name}
            if "login" in cur.lower() and "login" not in path.lower():
                findings.append(Finding("Authorization","MEDIUM",f"Redirected to login from {path}","Session expired?",endpoint=path,role=role_name))
            for err in info["errors"][:3]:
                findings.append(Finding("Functionality","MEDIUM",f"Error on {path}: {err[:60]}",err[:200],endpoint=path,role=role_name))
            for err in info["console_errors"][:3]:
                findings.append(Finding("JavaScript","LOW",f"JS error on {path}",err[:200],endpoint=path,role=role_name))
            self._explore_page(path, els, role_name)
            st = "PASSED" if not info["errors"] else "WARNING"
            self._add_result(f"GET {path}",st,f"Title:{info['title'][:40]} {desc} Links:{len(els['links'])}",
                             endpoint=path,role=role_name,findings=findings,duration=time.time()-start)
        for f in findings: self.findings.append(f)

    def _test_post_ep(self, path, role_name, desc):
        url = urljoin(self.base_url, path); start = time.time(); findings = []
        try:
            r = self.session.post(url, data={}, timeout=10)
            if r.status_code == 200:
                findings.append(Finding("Security","HIGH",f"POST {path} accepts empty without CSRF",f"Status:{r.status_code}",endpoint=path,role=role_name))
            elif r.status_code == 500:
                if any(w in r.text.lower()[:500] for w in ["traceback","exception"]):
                    findings.append(Finding("Security","MEDIUM",f"Error details leaked on {path}","Debug in 500",endpoint=path,role=role_name))
        except: pass
        try:
            csrf = None
            for c in self.session.cookies:
                if c.name == "csrftoken": csrf = c.value; break
            if csrf:
                r = self.session.post(url, data={"test":"invalid"}, headers={"X-CSRFToken":csrf,"Referer":url}, timeout=10)
                if r.status_code == 200 and "success" in r.text.lower():
                    findings.append(Finding("Functionality","MEDIUM",f"POST {path} accepts invalid data","Processed invalid payload",endpoint=path,role=role_name))
        except: pass
        self._add_result(f"POST-Check {path}","PASSED" if not findings else "WARNING",
                         f"{desc} {len(findings)} findings",endpoint=path,role=role_name,findings=findings,duration=time.time()-start)
        for f in findings: self.findings.append(f)

    def _explore_page(self, path, els, role_name):
        triggers = self.nav.find_els(By.CSS_SELECTOR,"[data-bs-toggle='modal'],[data-toggle='modal']",2)
        for tr in triggers[:5]:
            try:
                res = self.nav.interact_modal(tr)
                if res["opened"]:
                    self.logger.debug(f"    Modal: {res['title']} Form:{res['has_form']} Fields:{len(res['fields'])}")
            except: pass
        if els.get("tabs"):
            self.nav.interact_tabs(els["tabs"][:5])
        for link in els.get("links",[])[:20]:
            try:
                href = link.get_attribute("href")
                if (href and self.base_url in href and href not in self.discovered_pages
                        and len(self.discovered_pages) < self.MAX_DISCOVERED_PAGES):
                    self.discovered_pages.append(href)
            except: pass

    # ==================== API ENDPOINT TESTS ====================
    def test_api_endpoints(self, role_name="unauthenticated"):
        self.logger.info(f"  Testing API endpoints (as {role_name})...")
        for cat, endpoints in self.config.get("api_endpoints", {}).items():
            self.logger.info(f"    Category: {cat}")
            for ep in endpoints:
                method, path = ep.get("method","GET"), ep.get("path","")
                desc = ep.get("description","")
                is_router = ep.get("is_router", False)
                is_destructive = ep.get("destructive", False)
                is_sensitive = ep.get("sensitive", False)
                if is_destructive and self.skip_destructive:
                    self._add_result(f"API {method} {path}","SKIPPED","Destructive",endpoint=path,role=role_name); continue
                self._safe_exec(f"API-{method}-{path}", self._test_api_ep, method, path, desc,
                                is_router, is_sensitive, role_name, cat)
                self._throttle()

    def _test_api_ep(self, method, path, desc, is_router, is_sensitive, role_name, category):
        url = urljoin(self.base_url, path); start = time.time(); findings = []
        try:
            if method == "GET":
                resp = self.session.get(url, timeout=10)
            elif method == "POST":
                csrf = None
                for c in self.session.cookies:
                    if c.name == "csrftoken": csrf = c.value
                hdrs = {"X-CSRFToken": csrf} if csrf else {}
                resp = self.session.post(url, data={}, headers=hdrs, timeout=10)
            else:
                resp = self.session.request(method, url, timeout=10)

            sc = resp.status_code; ct = resp.headers.get("Content-Type",""); body = resp.text
            self.tested_endpoints[f"API:{path}"] = {"method":method,"status":sc,"content_type":ct,"role":role_name,"category":category}

            if sc == 200:
                if "json" in ct:
                    try:
                        data = resp.json()
                        self._analyze_json(path, data, role_name)
                        if isinstance(data, list) and len(data) > 100:
                            findings.append(Finding("API Security","MEDIUM",f"Large dataset ({len(data)} items) no pagination",
                                                    f"Endpoint: {path}",endpoint=path,role=role_name))
                        if is_sensitive:
                            findings.append(Finding("Data Exposure","HIGH",f"Sensitive data accessible: {desc}",
                                                    f"Endpoint: {path}",endpoint=path,role=role_name))
                    except json.JSONDecodeError:
                        findings.append(Finding("API","LOW",f"Invalid JSON from {path}",f"CT: {ct}",endpoint=path))
                self._check_sensitive(path, body[:5000], role_name)
            elif sc == 500:
                findings.append(Finding("Functionality","HIGH",f"Server error API {path}",f"500: {body[:150]}",endpoint=path,role=role_name))
                if any(w in body.lower() for w in ["traceback","exception","stack"]):
                    findings.append(Finding("Security","HIGH",f"Stack trace on {path}","Debug in 500",endpoint=path,role=role_name))

            if is_router and method == "GET":
                self._test_router_methods(path, role_name)
            self._test_api_unauth(path, method, role_name)

            st = "PASSED" if sc in (200,201,204,301,302,401,403) else "WARNING"
            self._add_result(f"API {method} {path}",st,f"Status:{sc} {desc}",endpoint=path,role=role_name,findings=findings,duration=time.time()-start)
            for f in findings: self.findings.append(f)
        except requests.exceptions.ConnectionError:
            self._add_result(f"API {method} {path}","ERROR","Connection refused",endpoint=path,duration=time.time()-start)
        except Exception as e:
            self._add_result(f"API {method} {path}","ERROR",str(e)[:200],endpoint=path,duration=time.time()-start)

    def _test_router_methods(self, path, role_name):
        for method in ["PUT","DELETE","PATCH"]:
            try:
                r = self.session.request(method, urljoin(self.base_url, path), timeout=10)
                if r.status_code not in (404,405,501):
                    sev = "HIGH" if r.status_code in (200,201,204) else "MEDIUM"
                    self._add_finding("API Security",sev,f"Router accepts {method}: {path}",
                                      f"Status:{r.status_code}",endpoint=path,role=role_name)
            except: pass
            self._throttle()

    def _test_api_unauth(self, path, method, role_name):
        try:
            s = requests.Session(); s.verify = False
            r = s.request(method if method == "GET" else "GET", urljoin(self.base_url, path), timeout=10)
            if r.status_code == 200:
                ct = r.headers.get("Content-Type","")
                if "json" in ct:
                    try:
                        data = r.json()
                        if data:
                            self._add_finding("Authorization","CRITICAL",f"API accessible without auth: {path}",
                                              f"Method:{method} Status:{r.status_code}",endpoint=path,role="unauthenticated")
                    except: pass
                elif "html" not in ct:
                    self._add_finding("Authorization","HIGH",f"API returns data without auth: {path}",
                                      f"CT:{ct}",endpoint=path,role="unauthenticated")
            s.close()
        except: pass

    def _analyze_json(self, path, data, role_name):
        try:
            js = json.dumps(data) if not isinstance(data, str) else data
            pii = {"Email":r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                   "Phone":r'\b(?:09|\+63)\d{9,10}\b', "SSN":r'\b\d{3}-\d{2}-\d{4}\b',
                   "Credit Card":r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'}
            for ptype, pat in pii.items():
                m = re.findall(pat, js)
                if m: self._add_finding("Data Exposure","HIGH",f"API exposes {ptype} ({len(m)})",
                                        f"Endpoint: {path}",endpoint=path,role=role_name)
            if isinstance(data, dict):
                keys = list(data.keys())
                sens = [k for k in keys if any(s in k.lower() for s in ["password","secret","token","key","credential","private","hash"])]
                if sens: self._add_finding("Data Exposure","CRITICAL",f"Sensitive fields: {', '.join(sens[:3])}",
                                           f"Endpoint: {path}",endpoint=path,role=role_name)
                internal = [k for k in keys if any(s in k.lower() for s in ["_id","created_at","updated_at","deleted_at"])]
                if len(internal) > 2:
                    self._add_finding("Data Exposure","LOW",f"Internal DB fields: {', '.join(internal[:3])}",
                                      f"Endpoint: {path}",endpoint=path,role=role_name)
                if any(k in data for k in ["error","debug","trace","stack","traceback"]):
                    self._add_finding("Information Disclosure","MEDIUM","Debug/error in API response",
                                      f"Endpoint: {path}",endpoint=path,role=role_name)
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                self._analyze_json(path, data[0], role_name)
        except: pass

    def _check_sensitive(self, path, body, role_name):
        try:
            pats = {"API Key":r'(?:api[_-]?key|apikey)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{20,})',
                    "JWT":r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
                    "AWS Key":r'AKIA[0-9A-Z]{16}',
                    "DB Conn":r'(?:mongodb|mysql|postgres|redis)://[^\s<>"\']+',
                    "Server Path":r'(?:/var/www|/home/\w+|C:\\\\|/etc/)',
                    "Stack Trace":r'(?:Traceback|File "[^"]+", line \d+)'}
            for name, pat in pats.items():
                if re.search(pat, body[:5000], re.IGNORECASE):
                    self._add_finding("Information Disclosure","HIGH",f"{name} in response",
                                      f"Endpoint: {path}",endpoint=path,role=role_name)
        except: pass

    # ==================== SECURITY TESTS ====================
    def test_idor(self, role_name):
        self.logger.info("  Testing IDOR vulnerabilities...")
        test_ids = [1,2,3,999,9999,0,-1]
        paths = ["/api/students/{id}/","/api/teachers/{id}/","/api/student-finances/{id}/",
                 "/api/student-schedules/{id}/","/api/courses/{id}/","/api/academic-terms/{id}/",
                 "/api/academic-history/{id}/"]
        for pt in paths:
            for tid in test_ids:
                path = pt.format(id=tid); url = urljoin(self.base_url, path)
                try:
                    r = self.session.get(url, timeout=10)
                    if r.status_code == 200 and r.text.strip():
                        try:
                            d = r.json()
                            if d: self._add_finding("IDOR","HIGH",f"Object accessible by ID: {path}",
                                                    f"ID={tid} accessible",endpoint=path,role=role_name)
                        except: pass
                    elif r.status_code == 500:
                        self._add_finding("Functionality","MEDIUM",f"500 for invalid ID: {path}",
                                          f"ID={tid}",endpoint=path,role=role_name)
                except: pass
                self._throttle()

    def test_xss(self, role_name):
        self.logger.info("  Testing XSS vulnerabilities...")
        payloads = ["<script>alert('XSS')</script>","'\"><img src=x onerror=alert(1)>",
                    "<svg/onload=alert(1)>","javascript:alert(1)"]
        test_paths = ["/academic_director/ad_subject_search/?q={p}","/?next={p}",
                      "/api/students/?search={p}","/api/courses/?search={p}"]
        for pt in test_paths:
            for pl in payloads[:2]:
                path = pt.format(p=quote(pl)); url = urljoin(self.base_url, path)
                try:
                    r = self.session.get(url, timeout=10)
                    if pl in r.text:
                        self._add_finding("XSS","HIGH","Reflected XSS: payload in response",
                                          f"Payload: {pl[:40]} Path: {path[:60]}",endpoint=path,role=role_name)
                except: pass
                self._throttle()
        if self.driver:
            try:
                for inp in self.nav.find_els(By.CSS_SELECTOR,"input[type='search'],input[name='q'],.search-input,#search",2)[:3]:
                    try:
                        self.nav.fill_input(inp, payloads[0]); inp.send_keys(Keys.RETURN); time.sleep(1)
                        if payloads[0] in self.driver.page_source:
                            self._add_finding("XSS","HIGH","Reflected XSS via search input",
                                              f"Payload reflected: {payloads[0][:40]}",role=role_name)
                    except: pass
            except: pass

    def test_sqli(self, role_name):
        self.logger.info("  Testing SQL injection...")
        payloads = ["'","\"","' OR '1'='1","1' ORDER BY 1--","' UNION SELECT NULL--"]
        err_pats = [r"SQL syntax.*MySQL",r"Warning.*mysql",r"PostgreSQL.*ERROR",r"ORA-\d+",
                    r"SQLite.*error",r"SQLSTATE",r"Unclosed quotation",r"syntax error"]
        test_paths = ["/api/students/?search={p}","/api/courses/?q={p}","/api/subjects/?filter={p}"]
        for pt in test_paths:
            for pl in payloads:
                path = pt.format(p=quote(pl)); url = urljoin(self.base_url, path)
                try:
                    r = self.session.get(url, timeout=10)
                    for ep in err_pats:
                        if re.search(ep, r.text, re.IGNORECASE):
                            self._add_finding("SQL Injection","CRITICAL","SQL error triggered",
                                              f"Payload: {pl} Pattern: {ep[:30]}",endpoint=path,role=role_name)
                            break
                    if r.status_code == 500 and ("sql" in r.text.lower() or "query" in r.text.lower()):
                        self._add_finding("SQL Injection","HIGH","Possible SQLi - 500 + SQL error",
                                          f"Payload: {pl}",endpoint=path,role=role_name)
                except: pass
                self._throttle()

    def test_csrf(self, role_name):
        self.logger.info("  Testing CSRF enforcement...")
        post_eps = []
        for mod_cfg in self.config.get("web_endpoints", {}).values():
            for ep in mod_cfg.get("endpoints", []):
                if ep.get("method") == "POST": post_eps.append(ep.get("path",""))
        auth_eps = self.config.get("authentication", {})
        for k, v in auth_eps.items():
            if isinstance(v, dict) and v.get("method") == "POST":
                post_eps.append(v.get("path",""))
        tested = set()
        for path in post_eps[:30]:
            if path in tested: continue
            tested.add(path)
            url = urljoin(self.base_url, path)
            try:
                s = requests.Session(); s.verify = False
                r = s.post(url, data={"test":"csrf_check"}, timeout=10)
                if r.status_code == 200:
                    self._add_finding("CSRF","HIGH",f"POST {path} no CSRF enforcement",
                                      f"Status:{r.status_code}",endpoint=path,role=role_name)
                elif r.status_code != 403:
                    self._add_finding("CSRF","MEDIUM",f"POST {path} unexpected response without CSRF",
                                      f"Status:{r.status_code}",endpoint=path,role=role_name)
                s.close()
            except: pass
            self._throttle()

    def test_rate_limiting(self, role_name):
        self.logger.info("  Testing rate limiting...")
        targets = ["/","/check_email_existence/","/verify_otp/"]
        for path in targets:
            url = urljoin(self.base_url, path)
            statuses = []
            try:
                for _ in range(20):
                    r = self.session.get(url, timeout=5) if path == "/" else self.session.post(url, data={}, timeout=5)
                    statuses.append(r.status_code)
                if 429 not in statuses:
                    self._add_finding("Rate Limiting","MEDIUM",f"No rate limiting on {path}",
                                      f"20 rapid requests all accepted",endpoint=path,role=role_name)
            except: pass

    def test_http_methods(self, role_name):
        self.logger.info("  Testing HTTP methods...")
        for path in ["/","/api/students/","/api/courses/"]:
            url = urljoin(self.base_url, path)
            for method in ["PUT","DELETE","TRACE","OPTIONS"]:
                try:
                    r = self.session.request(method, url, timeout=10)
                    if method == "OPTIONS" and r.status_code == 200:
                        allow = r.headers.get("Allow","")
                        if allow: self._add_finding("HTTP Methods","INFO",f"OPTIONS reveals: {allow}",
                                                    f"Path: {path}",endpoint=path,role=role_name)
                    elif method == "TRACE" and r.status_code == 200:
                        self._add_finding("HTTP Methods","MEDIUM",f"TRACE enabled on {path}",
                                          "May allow XST attacks",endpoint=path,role=role_name)
                    elif method in ("PUT","DELETE") and r.status_code in (200,201,204):
                        self._add_finding("HTTP Methods","HIGH",f"{method} accepted on {path}",
                                          f"Status:{r.status_code}",endpoint=path,role=role_name)
                except: pass
                self._throttle()

    def test_path_traversal(self, role_name):
        self.logger.info("  Testing path traversal...")
        payloads = ["../../../etc/passwd","....//....//....//etc/passwd",
                    "..%2f..%2f..%2fetc%2fpasswd","..\\..\\..\\windows\\system32\\config\\sam"]
        for pl in payloads:
            url = urljoin(self.base_url, f"/{quote(pl)}")
            try:
                r = self.session.get(url, timeout=10)
                if r.status_code == 200 and ("root:" in r.text or "[boot loader]" in r.text):
                    self._add_finding("Path Traversal","CRITICAL","Path traversal successful",
                                      f"Payload: {pl}",role=role_name)
                elif r.status_code == 200 and len(r.text) > 0:
                    if any(w in r.text.lower() for w in ["root:","daemon:","bin:","www-data"]):
                        self._add_finding("Path Traversal","CRITICAL","System file contents exposed",
                                          f"Payload: {pl}",role=role_name)
            except: pass
            self._throttle()

    def test_open_redirect(self, role_name):
        self.logger.info("  Testing open redirect...")
        for param in ["next","redirect","url","return","returnTo","continue"]:
            url = urljoin(self.base_url, f"/?{param}=https://evil.com")
            try:
                r = self.session.get(url, timeout=10, allow_redirects=False)
                if r.status_code in (301,302,303,307) and "evil.com" in r.headers.get("Location",""):
                    self._add_finding("Open Redirect","HIGH",f"Open redirect via '{param}' param",
                                      f"Redirects to evil.com",endpoint=f"/?{param}=",role=role_name)
            except: pass
            self._throttle()

    # ==================== SMART PAGE CRAWLER ====================
    def crawl_discovered_pages(self, role_name):
        self.logger.info(f"  Crawling {len(self.discovered_pages)} discovered pages...")
        visited = set()
        for page_url in self.discovered_pages[:50]:
            if page_url in visited: continue
            visited.add(page_url)
            parsed = urlparse(page_url)
            path = parsed.path
            try:
                self.nav.navigate(page_url)
                time.sleep(0.3)
                info = self.nav.get_page_info()
                els = self.nav.detect_elements()
                findings = []
                if info["errors"]:
                    for err in info["errors"][:2]:
                        findings.append(Finding("Functionality","MEDIUM",f"Error on discovered page {path}",
                                                err[:200],endpoint=path,role=role_name))
                if info["console_errors"]:
                    for err in info["console_errors"][:2]:
                        findings.append(Finding("JavaScript","LOW",f"JS error on {path}",
                                                err[:200],endpoint=path,role=role_name))
                st = "PASSED" if not info["errors"] else "WARNING"
                self._add_result(f"Crawl {path}",st,f"Title:{info['title'][:40]}",
                                 endpoint=path,role=role_name,findings=findings)
                for f in findings: self.findings.append(f)
                # Discover more links
                for link in els.get("links",[])[:10]:
                    try:
                        href = link.get_attribute("href")
                        if (href and self.base_url in href and href not in self.discovered_pages
                                and href not in visited
                                and len(self.discovered_pages) < self.MAX_DISCOVERED_PAGES):
                            self.discovered_pages.append(href)
                    except: pass
            except: pass
            self._throttle()

    # ==================== RUN SCAN ====================
    def run_scan(self):
        self.start_time = datetime.now()
        self.logger.info("=" * 70)
        self.logger.info(f"  RMS Selenium Test Suite v{self.VERSION}")
        self.logger.info(f"  Target: {self.base_url}")
        self.logger.info(f"  Browser: {self.browser_name} | Headless: {self.headless}")
        self.logger.info(f"  Skip Destructive: {self.skip_destructive}")
        self.logger.info(f"  Platform: {platform.system()} {platform.release()}")
        self.logger.info(f"  Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 70)

        try:
            self._init_driver()
        except Exception as e:
            self.logger.critical(f"Browser init failed: {e}")
            self._add_finding("Setup","CRITICAL","Browser initialization failed",str(e))
            self.end_time = datetime.now()
            self._generate_report()
            return

        # Phase 1: Pre-auth tests
        self.logger.info("\n" + "=" * 60)
        self.logger.info("PHASE 1: Pre-Authentication Tests")
        self.logger.info("=" * 60)
        self._safe_exec("LoginPage", self.test_login_page)
        self._safe_exec("LoginSecurity", self.test_login_security)
        self._safe_exec("PasswordReset", self.test_password_reset)
        self._safe_exec("RateLimiting-PreAuth", self.test_rate_limiting, "unauthenticated")
        self._safe_exec("OpenRedirect", self.test_open_redirect, "unauthenticated")
        self._safe_exec("PathTraversal", self.test_path_traversal, "unauthenticated")
        self._safe_exec("HTTPMethods-PreAuth", self.test_http_methods, "unauthenticated")

        # Phase 2: Unauthenticated API tests
        self.logger.info("\n" + "=" * 60)
        self.logger.info("PHASE 2: Unauthenticated API Tests")
        self.logger.info("=" * 60)
        self._safe_exec("API-Unauth", self.test_api_endpoints, "unauthenticated")
        self._safe_exec("CSRF-Unauth", self.test_csrf, "unauthenticated")

        self.logger.info("\n" + "=" * 60)
        self.logger.info("PHASE 2B: Admin Provisioning of Generated Role Accounts")
        self.logger.info("=" * 60)
        self._safe_exec("Provision-Generated-Roles", self.provision_role_accounts)

        # Phase 3: Per-role tests
        roles = self.config.get("roles", [])
        if self.roles_filter:
            filter_set = set(r.lower().replace(" ","_") for r in self.roles_filter)
            roles = [r for r in roles if r.get("slug","").lower() in filter_set or r.get("name","").lower().replace(" ","_") in filter_set]

        for role_cfg in roles:
            role_name = role_cfg.get("name", role_cfg.get("slug","unknown"))
            role_slug = role_cfg.get("slug", role_name.lower().replace(" ","_"))
            self.logger.info("\n" + "=" * 60)
            self.logger.info(f"PHASE 3: Testing Role - {role_name}")
            self.logger.info("=" * 60)

            logged_in = self._safe_exec(f"Login-{role_name}", self.test_login_with_role, role_cfg)
            if logged_in is None: logged_in = False

            if logged_in:
                self._safe_exec(f"RBAC-{role_name}", self.test_rbac, role_cfg, logged_in)
                self._safe_exec(f"WebEP-{role_name}", self.test_web_endpoints, role_name, role_slug)
                self._safe_exec(f"API-{role_name}", self.test_api_endpoints, role_name)
                self._safe_exec(f"IDOR-{role_name}", self.test_idor, role_name)
                self._safe_exec(f"XSS-{role_name}", self.test_xss, role_name)
                self._safe_exec(f"SQLi-{role_name}", self.test_sqli, role_name)
                self._safe_exec(f"CSRF-{role_name}", self.test_csrf, role_name)
                self._safe_exec(f"Crawl-{role_name}", self.crawl_discovered_pages, role_name)
                self._safe_exec(f"Logout-{role_name}", self.test_logout)
            else:
                self.logger.info(f"  Skipping authenticated tests for {role_name} (login failed)")

        # Cleanup
        self.end_time = datetime.now()
        try:
            if self.driver: self.driver.quit()
        except: pass

        self.logger.info("\n" + "=" * 60)
        self.logger.info("GENERATING REPORT")
        self.logger.info("=" * 60)
        self._generate_report()

    # ==================== REPORT GENERATION ====================
    def _generate_report(self):
        duration = (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0
        # Severity counts
        sev_counts = defaultdict(int)
        for f in self.findings: sev_counts[f.severity] += 1
        # Status counts
        stat_counts = defaultdict(int)
        for r in self.results: stat_counts[r.status] += 1
        # Category counts
        cat_counts = defaultdict(int)
        for f in self.findings: cat_counts[f.category] += 1

        summary = {
            "meta": {
                "tool": "RMS Selenium Test Suite",
                "version": self.VERSION,
                "target": self.base_url,
                "browser": self.browser_name,
                "platform": f"{platform.system()} {platform.release()}",
                "start_time": self.start_time.isoformat() if self.start_time else "",
                "end_time": self.end_time.isoformat() if self.end_time else "",
                "duration_seconds": round(duration, 2),
                "headless": self.headless,
                "skip_destructive": self.skip_destructive,
            },
            "summary": {
                "total_tests": len(self.results),
                "passed": stat_counts.get("PASSED",0),
                "failed": stat_counts.get("FAILED",0),
                "errors": stat_counts.get("ERROR",0),
                "warnings": stat_counts.get("WARNING",0),
                "skipped": stat_counts.get("SKIPPED",0),
                "total_findings": len(self.findings),
                "critical": sev_counts.get("CRITICAL",0),
                "high": sev_counts.get("HIGH",0),
                "medium": sev_counts.get("MEDIUM",0),
                "low": sev_counts.get("LOW",0),
                "info": sev_counts.get("INFO",0),
                "endpoints_tested": len(self.tested_endpoints),
                "pages_discovered": len(self.discovered_pages),
            },
            "findings_by_category": dict(cat_counts),
            "findings": [asdict(f) for f in self.findings],
            "test_results": [asdict(r) for r in self.results],
            "tested_endpoints": self.tested_endpoints,
            "discovered_pages": self.discovered_pages[:100],
            "mock_database_used": self.mock_db.export(),
        }

        # Save JSON report
        os.makedirs(self.output_dir, exist_ok=True)
        json_path = os.path.join(self.output_dir, "rms_test_report.json")
        with open(json_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        self.logger.info(f"JSON report: {json_path}")

        # Save HTML report
        html_path = os.path.join(self.output_dir, "rms_test_report.html")
        self._generate_html_report(summary, html_path)
        self.logger.info(f"HTML report: {html_path}")

        # Console summary
        self.logger.info("\n" + "=" * 70)
        self.logger.info("  TEST SUITE COMPLETE")
        self.logger.info("=" * 70)
        self.logger.info(f"  Duration: {duration:.1f}s")
        self.logger.info(f"  Tests: {len(self.results)} | Passed: {stat_counts.get('PASSED',0)} | Failed: {stat_counts.get('FAILED',0)} | Errors: {stat_counts.get('ERROR',0)}")
        self.logger.info(f"  Findings: {len(self.findings)} | CRITICAL: {sev_counts.get('CRITICAL',0)} | HIGH: {sev_counts.get('HIGH',0)} | MEDIUM: {sev_counts.get('MEDIUM',0)} | LOW: {sev_counts.get('LOW',0)}")
        self.logger.info(f"  Endpoints tested: {len(self.tested_endpoints)} | Pages discovered: {len(self.discovered_pages)}")
        self.logger.info(f"  Reports: {self.output_dir}")
        self.logger.info("=" * 70)

    def _generate_html_report(self, data, path):
        sev_colors = {"CRITICAL":"#dc3545","HIGH":"#fd7e14","MEDIUM":"#ffc107","LOW":"#17a2b8","INFO":"#6c757d"}
        stat_colors = {"PASSED":"#28a745","FAILED":"#dc3545","ERROR":"#fd7e14","WARNING":"#ffc107","SKIPPED":"#6c757d"}
        s = data["summary"]
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>RMS Test Report - {data['meta']['target']}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1a1a2e;color:#e0e0e0;line-height:1.6}}
.container{{max-width:1200px;margin:0 auto;padding:20px}}
h1{{color:#00d4ff;margin-bottom:5px}}
h2{{color:#00d4ff;margin:30px 0 15px;border-bottom:2px solid #16213e;padding-bottom:8px}}
h3{{color:#e94560;margin:20px 0 10px}}
.meta{{color:#888;font-size:0.9em;margin-bottom:20px}}
.summary-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin:20px 0}}
.summary-card{{background:#16213e;border-radius:10px;padding:20px;text-align:center;border:1px solid #0f3460}}
.summary-card .number{{font-size:2.5em;font-weight:bold}}
.summary-card .label{{font-size:0.85em;color:#888;margin-top:5px}}
.findings-table,.results-table{{width:100%;border-collapse:collapse;margin:15px 0}}
.findings-table th,.results-table th{{background:#0f3460;padding:12px;text-align:left;font-weight:600}}
.findings-table td,.results-table td{{padding:10px 12px;border-bottom:1px solid #16213e;font-size:0.9em}}
.findings-table tr:hover,.results-table tr:hover{{background:#16213e}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.8em;font-weight:600;color:#fff}}
.filter-bar{{margin:15px 0;display:flex;gap:8px;flex-wrap:wrap}}
.filter-btn{{padding:6px 14px;border:1px solid #0f3460;background:#16213e;color:#e0e0e0;border-radius:6px;cursor:pointer;font-size:0.85em}}
.filter-btn:hover,.filter-btn.active{{background:#0f3460;color:#00d4ff}}
.detail{{max-width:400px;word-wrap:break-word;font-size:0.85em;color:#aaa}}
.ep{{font-family:monospace;font-size:0.85em;color:#00d4ff}}
</style>
</head>
<body>
<div class="container">
<h1>RMS Selenium Test Report</h1>
<p class="meta">Target: {data['meta']['target']} | Browser: {data['meta']['browser']} | Platform: {data['meta']['platform']} | Duration: {data['meta']['duration_seconds']}s | {data['meta'].get('start_time','')[:19]}</p>

<h2>Summary</h2>
<div class="summary-grid">
<div class="summary-card"><div class="number" style="color:#00d4ff">{s['total_tests']}</div><div class="label">Total Tests</div></div>
<div class="summary-card"><div class="number" style="color:#28a745">{s['passed']}</div><div class="label">Passed</div></div>
<div class="summary-card"><div class="number" style="color:#dc3545">{s['failed']}</div><div class="label">Failed</div></div>
<div class="summary-card"><div class="number" style="color:#fd7e14">{s['errors']}</div><div class="label">Errors</div></div>
<div class="summary-card"><div class="number" style="color:#ffc107">{s['warnings']}</div><div class="label">Warnings</div></div>
<div class="summary-card"><div class="number" style="color:#dc3545">{s['critical']}</div><div class="label">Critical Findings</div></div>
<div class="summary-card"><div class="number" style="color:#fd7e14">{s['high']}</div><div class="label">High Findings</div></div>
<div class="summary-card"><div class="number" style="color:#ffc107">{s['medium']}</div><div class="label">Medium Findings</div></div>
</div>

<h2>Security Findings ({s['total_findings']})</h2>
<div class="filter-bar">
<button class="filter-btn active" onclick="filterFindings('all')">All</button>
<button class="filter-btn" onclick="filterFindings('CRITICAL')">Critical ({s['critical']})</button>
<button class="filter-btn" onclick="filterFindings('HIGH')">High ({s['high']})</button>
<button class="filter-btn" onclick="filterFindings('MEDIUM')">Medium ({s['medium']})</button>
<button class="filter-btn" onclick="filterFindings('LOW')">Low ({s['low']})</button>
</div>
<table class="findings-table" id="findingsTable">
<tr><th>Severity</th><th>Category</th><th>Title</th><th>Detail</th><th>Endpoint</th><th>Role</th></tr>
"""
        for f in data["findings"]:
            color = sev_colors.get(f["severity"],"#888")
            html += f"""<tr data-severity="{f['severity']}">
<td><span class="badge" style="background:{color}">{f['severity']}</span></td>
<td>{f['category']}</td><td>{f['title'][:80]}</td>
<td class="detail">{f['detail'][:120]}</td><td class="ep">{f['endpoint'][:50]}</td><td>{f['role']}</td></tr>\n"""

        html += """</table>
<h2>Test Results</h2>
<table class="results-table">
<tr><th>Test</th><th>Status</th><th>Message</th><th>Endpoint</th><th>Role</th><th>Duration</th></tr>
"""
        for r in data["test_results"]:
            color = stat_colors.get(r["status"],"#888")
            html += f"""<tr><td>{r['test_name'][:60]}</td>
<td><span class="badge" style="background:{color}">{r['status']}</span></td>
<td class="detail">{r['message'][:100]}</td><td class="ep">{r['endpoint'][:50]}</td>
<td>{r['role']}</td><td>{r['duration']:.2f}s</td></tr>\n"""

        html += f"""</table>
<h2>Findings by Category</h2>
<div class="summary-grid">
"""
        for cat, count in sorted(data.get("findings_by_category",{}).items(), key=lambda x:-x[1]):
            html += f'<div class="summary-card"><div class="number" style="color:#e94560">{count}</div><div class="label">{cat}</div></div>\n'

        html += f"""</div>
<h2>Discovered Pages ({len(data.get('discovered_pages',[]))})</h2>
<ul style="list-style:none;padding:0">
"""
        for pg in data.get("discovered_pages",[])[:50]:
            html += f'<li class="ep" style="padding:3px 0">{pg}</li>\n'

        html += """</ul>
</div>
<script>
function filterFindings(severity) {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('#findingsTable tr[data-severity]').forEach(row => {
        row.style.display = (severity === 'all' || row.dataset.severity === severity) ? '' : 'none';
    });
}
</script>
</body></html>"""
        with open(path, "w") as f:
            f.write(html)


# ============================================================
# MAIN ENTRY POINT
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="RMS Selenium Test Suite v1.0 - Comprehensive automated testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python rms_selenium_test.py --url http://localhost:8000
  python rms_selenium_test.py --url http://localhost:8000 --headless
  python rms_selenium_test.py --url http://localhost:8000 --roles admin,teacher
  python rms_selenium_test.py --url http://localhost:8000 --skip-destructive --browser firefox
  python rms_selenium_test.py --url http://localhost:8000 --config rms_test_config.json --delay 1.0
""")
    parser.add_argument("--url", required=True, help="Target RMS base URL (e.g. http://localhost:8000)")
    parser.add_argument("--config", default=None, help="Path to test config JSON (default: rms_test_config.json)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--browser", default="chrome", choices=["chrome","firefox","edge"], help="Browser to use (default: chrome)")
    parser.add_argument("--roles", default=None, help="Comma-separated roles to test (default: all)")
    parser.add_argument("--skip-destructive", action="store_true", help="Skip destructive POST/PUT/DELETE tests")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests in seconds (default: 0.5)")
    parser.add_argument("--output", default=None, help="Output directory for reports (default: rms_test_results)")

    args = parser.parse_args()
    roles_filter = [r.strip() for r in args.roles.split(",")] if args.roles else None

    suite = RMSTestSuite(
        base_url=args.url,
        config_path=args.config,
        headless=args.headless,
        browser=args.browser,
        roles_filter=roles_filter,
        skip_destructive=args.skip_destructive,
        delay=args.delay,
        output_dir=args.output,
    )
    suite.run_scan()


if __name__ == "__main__":
    main()
