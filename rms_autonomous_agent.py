#!/usr/bin/env python3
"""
Universal Web Security & Performance Auditor
Heuristic-Driven Autonomous Agent v2.0

A graph-based, semantically-aware Selenium engine that:
  - Maps DOM at runtime via ARIA roles and UX patterns
  - Tracks navigation state via a breadcrumb state machine
  - Pierces Shadow DOM / Web Components
  - Probes horizontal & vertical privilege escalation
  - Fuzzes with polyglot payloads across all inputs
  - Extracts Navigation Timing API performance metrics
  - Correlates security surfaces with slow-loading pages

Usage:
  python rms_autonomous_agent.py --url http://localhost:8000 --headless
  python rms_autonomous_agent.py --url http://localhost:8000 --roles admin,teacher --browser firefox
  python rms_autonomous_agent.py --url http://localhost:8000 --skip-destructive --output ./reports
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import logging
import math
import os
import platform
import random
import re
import sys
import time
import traceback
import urllib.parse
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlencode, parse_qs

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        ElementClickInterceptedException, ElementNotInteractableException,
        NoAlertPresentException, NoSuchElementException, NoSuchFrameException,
        StaleElementReferenceException, TimeoutException, WebDriverException,
        JavascriptException,
    )
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import Select, WebDriverWait
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False
    print("[WARN] selenium not installed. Run: pip install selenium webdriver-manager", file=sys.stderr)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    WDM_OK = True
except ImportError:
    WDM_OK = False

try:
    from ui_control_driver import UIControlDriver
    UICTRL_OK = True
except ImportError:
    UICTRL_OK = False

# ─────────────────────────────────────────────
#  CONSTANTS & ENUMERATIONS
# ─────────────────────────────────────────────

VERSION = "2.0"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

POLYGLOT_PAYLOADS = [
    "jaVasCript:/*-/*`/*\\`/*'/*\"/**/(/* */oNcliCk=alert(1))//%0D%0A%0d%0a//</stYle/</titLe/</teXtarEa/</scRipt/--!>\\x3csVg/<sVg/oNloAd=alert(1)//",
    "'\"><img src=x onerror=alert(document.domain)>",
    "<svg/onload=alert(1)>",
    "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//\"",
    "' OR '1'='1' --",
    "' UNION SELECT NULL,NULL,NULL --",
    "1' ORDER BY 10 --",
    "\" OR \"1\"=\"1",
    "../../../../../../etc/passwd",
    "..%2f..%2f..%2fetc%2fpasswd",
    "${7*7}",
    "{{7*7}}",
    "<%=7*7%>",
    "';!--\"<XSS>=&{()}",
]

XSS_PAYLOADS = [
    "<script>alert('XSS')</script>",
    "'\"><img src=x onerror=alert(1)>",
    "<svg/onload=alert(1)>",
    "<details open ontoggle=alert(1)>",
    "javascript:alert(1)",
    "<iframe src=javascript:alert(1)>",
    "<body onload=alert(1)>",
    "<input autofocus onfocus=alert(1)>",
]

SQLI_PAYLOADS = [
    "'", '"', "' OR '1'='1", "' OR 1=1 --", "\" OR \"1\"=\"1",
    "' UNION SELECT NULL --", "1; DROP TABLE users --",
    "' AND SLEEP(1) --", "1' ORDER BY 100 --",
]

PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd", "....//....//....//etc//passwd",
    "..%2f..%2f..%2fetc%2fpasswd", "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "..\\..\\..\\windows\\win.ini", "..%5c..%5c..%5cwindows%5cwin.ini",
]

SSTI_PAYLOADS = ["{{7*7}}", "${7*7}", "#{7*7}", "<%= 7*7 %>", "{% 7*7 %}"]

DISMISSAL_PATTERNS = {
    "text": ["close", "dismiss", "cancel", "later", "no thanks", "skip", "ok", "got it",
             "accept", "agree", "x", "✕", "✗", "deny", "continue"],
    "aria": ["dialog", "alertdialog"],
    "selectors": [
        "button[aria-label*='close' i]", "button[aria-label*='dismiss' i]",
        "[data-dismiss]", "[data-bs-dismiss]", ".modal-close", ".close-btn",
        ".btn-close", "#close-modal", ".swal2-confirm", ".alert-close",
        "[class*='close']", "[id*='close']", "[class*='dismiss']",
    ],
}

SQL_ERROR_PATTERNS = [
    r"SQL syntax.*MySQL", r"Warning.*mysql_", r"PostgreSQL.*ERROR", r"ORA-\d{5}",
    r"SQLite.*error", r"SQLSTATE\[", r"Unclosed quotation mark",
    r"syntax error.*near", r"mysql_fetch", r"pg_query", r"sqlite3\.OperationalError",
]


# ─────────────────────────────────────────────
#  DATA CLASSES
# ─────────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"
    INFO     = "INFO"


class NodeType(str, Enum):
    NAVIGATION       = "NAVIGATION"
    DATA_ENTRY       = "DATA_ENTRY"
    DESTRUCTIVE      = "DESTRUCTIVE"
    ACCOUNT_MGMT     = "ACCOUNT_MGMT"
    DISPLAY          = "DISPLAY"
    UNKNOWN          = "UNKNOWN"


class PageState(str, Enum):
    FULL_PAGE    = "FULL_PAGE"
    FRAGMENT     = "FRAGMENT"    # URL changed but no full reload
    MODAL        = "MODAL"       # DOM changed, URL same, modal open
    REDIRECT     = "REDIRECT"
    ERROR        = "ERROR"


@dataclass
class InteractableNode:
    tag: str
    node_type: NodeType
    label: str
    selector: str
    href: Optional[str] = None
    action: Optional[str] = None
    method: Optional[str] = None
    is_destructive: bool = False
    depth: int = 0


@dataclass
class BreadcrumbState:
    url: str
    title: str
    state: PageState
    dom_hash: str
    timestamp: float = field(default_factory=time.time)
    role: str = "unauthenticated"
    parent_url: Optional[str] = None
    modal_title: Optional[str] = None


@dataclass
class PerformanceMetrics:
    url: str
    ttfb_ms: float = 0.0
    dom_content_loaded_ms: float = 0.0
    fully_loaded_ms: float = 0.0
    first_paint_ms: float = 0.0
    resource_count: int = 0
    heavy_resources: List[Dict] = field(default_factory=list)
    total_transfer_kb: float = 0.0
    grade: str = "N/A"
    timestamp: float = field(default_factory=time.time)


@dataclass
class SecurityFinding:
    severity: str
    category: str
    title: str
    detail: str
    endpoint: str = ""
    role: str = ""
    payload: str = ""
    evidence: str = ""
    perf_correlated: bool = False
    perf_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TestResult:
    test_name: str
    status: str           # PASSED / FAILED / WARNING / ERROR / SKIPPED
    message: str
    endpoint: str = ""
    role: str = ""
    duration: float = 0.0
    findings_count: int = 0


# ─────────────────────────────────────────────
#  SEMANTIC MAPPER  — "The Thinking Layer"
# ─────────────────────────────────────────────

class SemanticMapper:
    """
    Analyses the live DOM and produces a graph of InteractableNodes.
    Uses ARIA roles, semantic HTML, and common UX heuristics —
    never relies on hard-coded IDs.
    """

    NAV_KEYWORDS      = {"nav","home","dashboard","menu","sidebar","header","breadcrumb","link"}
    DESTRUCT_KEYWORDS = {"delete","remove","destroy","drop","purge","wipe","terminate","revoke","ban","suspend"}
    ACCOUNT_KEYWORDS  = {"login","logout","sign in","sign out","register","profile","account","password","reset",
                         "credential","auth","session","user","role","permission"}
    ENTRY_TAGS        = {"input","textarea","select","[contenteditable]"}

    def __init__(self, driver):
        self.driver = driver

    def map_page(self) -> List[InteractableNode]:
        nodes: List[InteractableNode] = []
        try:
            nodes += self._map_links()
            nodes += self._map_buttons()
            nodes += self._map_forms()
            nodes += self._map_aria_widgets()
            nodes += self._pierce_shadow_roots()
        except Exception:
            pass
        return nodes

    def _label(self, el) -> str:
        for attr in ("aria-label","title","placeholder","alt","name","id","value","data-original-title"):
            try:
                v = el.get_attribute(attr)
                if v and v.strip(): return v.strip()[:80]
            except: pass
        try:
            t = el.text
            if t and t.strip(): return t.strip()[:80]
        except: pass
        try:
            return self.driver.execute_script(
                "var e=arguments[0];return e.innerText||e.textContent||'';", el).strip()[:80]
        except: return "unknown"

    def _classify(self, label: str, tag: str, href: str = "") -> NodeType:
        l = label.lower(); h = href.lower()
        if any(k in l or k in h for k in self.DESTRUCT_KEYWORDS): return NodeType.DESTRUCTIVE
        if any(k in l or k in h for k in self.ACCOUNT_KEYWORDS):  return NodeType.ACCOUNT_MGMT
        if tag in ("a","nav") or any(k in l or k in h for k in self.NAV_KEYWORDS): return NodeType.NAVIGATION
        if tag in ("input","textarea","select","form"): return NodeType.DATA_ENTRY
        return NodeType.UNKNOWN

    def _safe_attr(self, el, attr: str) -> str:
        try: return el.get_attribute(attr) or ""
        except: return ""

    def _css_path(self, el) -> str:
        try:
            return self.driver.execute_script("""
                var el=arguments[0],path=[];
                while(el&&el.nodeType===1){
                    var s=el.nodeName.toLowerCase();
                    if(el.id){s+='#'+el.id;path.unshift(s);break;}
                    var i=1,sib=el;
                    while(sib=sib.previousElementSibling) i++;
                    if(i>1) s+=':nth-child('+i+')';
                    path.unshift(s);el=el.parentNode;
                } return path.slice(-4).join(' > ');""", el)
        except: return "unknown"

    def _map_links(self) -> List[InteractableNode]:
        nodes = []
        try:
            links = self.driver.find_elements(By.TAG_NAME, "a")[:60]
            for el in links:
                href = self._safe_attr(el, "href")
                label = self._label(el)
                nt = self._classify(label, "a", href)
                nodes.append(InteractableNode("a", nt, label, self._css_path(el),
                                              href=href, is_destructive=(nt==NodeType.DESTRUCTIVE)))
        except: pass
        return nodes

    def _map_buttons(self) -> List[InteractableNode]:
        nodes = []
        sel = "button, input[type='submit'], input[type='button'], input[type='reset'], [role='button'], [onclick]"
        try:
            for el in self.driver.find_elements(By.CSS_SELECTOR, sel)[:40]:
                label = self._label(el)
                tag = self._safe_attr(el,"tagName").lower() or "button"
                nt = self._classify(label, tag)
                nodes.append(InteractableNode(tag, nt, label, self._css_path(el),
                                              is_destructive=(nt==NodeType.DESTRUCTIVE)))
        except: pass
        return nodes

    def _map_forms(self) -> List[InteractableNode]:
        nodes = []
        try:
            for form in self.driver.find_elements(By.TAG_NAME, "form")[:20]:
                action = self._safe_attr(form, "action")
                method = (self._safe_attr(form, "method") or "GET").upper()
                label  = self._label(form) or action or "form"
                nt = self._classify(label, "form", action)
                nodes.append(InteractableNode("form", nt, label, self._css_path(form),
                                              action=action, method=method))
                for inp in form.find_elements(By.CSS_SELECTOR, "input,textarea,select")[:10]:
                    ilabel = self._label(inp)
                    nodes.append(InteractableNode(
                        self._safe_attr(inp,"tagName").lower() or "input",
                        NodeType.DATA_ENTRY, ilabel, self._css_path(inp)))
        except: pass
        return nodes

    def _map_aria_widgets(self) -> List[InteractableNode]:
        nodes = []
        roles_to_map = ["tab","menuitem","option","treeitem","row","gridcell","combobox","listbox","dialog"]
        for role in roles_to_map:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, f"[role='{role}']")[:10]:
                    label = self._label(el)
                    nodes.append(InteractableNode(role, NodeType.NAVIGATION, label, self._css_path(el)))
            except: pass
        return nodes

    def _pierce_shadow_roots(self) -> List[InteractableNode]:
        nodes = []
        try:
            hosts = self.driver.find_elements(By.CSS_SELECTOR, "*")
            for host in hosts[:200]:
                try:
                    shadow = self.driver.execute_script("return arguments[0].shadowRoot;", host)
                    if not shadow: continue
                    items = self.driver.execute_script(
                        "return Array.from(arguments[0].querySelectorAll('a,button,input,form,[role]'));", shadow)
                    for el in (items or [])[:10]:
                        try:
                            tag   = self.driver.execute_script("return arguments[0].tagName;", el).lower()
                            label = self.driver.execute_script(
                                "return arguments[0].innerText||arguments[0].placeholder||arguments[0].name||'shadow-node';", el)
                            nt = self._classify(label or "", tag)
                            nodes.append(InteractableNode(tag, nt, f"[shadow] {label or tag}",
                                                          "shadow-root", is_destructive=(nt==NodeType.DESTRUCTIVE)))
                        except: pass
                except: pass
        except: pass
        return nodes


# ─────────────────────────────────────────────
#  STATE TRACKER  — Breadcrumb / State Machine
# ─────────────────────────────────────────────

class StateTracker:
    """
    Tracks navigation as a graph of BreadcrumbState nodes.
    Detects full-page loads, fragment transitions, and modal overlays.
    """

    def __init__(self, driver):
        self.driver = driver
        self.history: List[BreadcrumbState] = []
        self.visited_urls: Set[str] = set()
        self.discovered_admin_urls: Set[str] = set()
        self._prev_url: str = ""
        self._prev_dom_hash: str = ""

    def _dom_hash(self) -> str:
        try:
            body = self.driver.execute_script("return document.body.innerHTML;")
            return hashlib.md5((body or "").encode()).hexdigest()
        except: return ""

    def _modal_open(self) -> Optional[str]:
        try:
            for sel in ["[role='dialog']","[role='alertdialog']",
                        ".modal.show",".modal.in","[aria-modal='true']",
                        ".swal2-popup",".ui-dialog","[data-modal]"]:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    if el.is_displayed():
                        t = el.find_elements(By.CSS_SELECTOR, ".modal-title,.dialog-title,h2,h3")
                        return (t[0].text if t else "modal")
        except: pass
        return None

    def snapshot(self, role: str = "unauthenticated") -> BreadcrumbState:
        try:
            url   = self.driver.current_url
            title = self.driver.title
        except:
            url, title = "", ""
        dom_hash = self._dom_hash()
        modal    = self._modal_open()

        if modal:
            state = PageState.MODAL
        elif url != self._prev_url:
            state = PageState.FULL_PAGE
        elif dom_hash != self._prev_dom_hash:
            state = PageState.FRAGMENT
        else:
            state = PageState.FULL_PAGE

        parent = self.history[-1].url if self.history else None
        bc = BreadcrumbState(url=url, title=title, state=state, dom_hash=dom_hash,
                             role=role, parent_url=parent, modal_title=modal)
        self.history.append(bc)
        self.visited_urls.add(url)
        self._prev_url      = url
        self._prev_dom_hash = dom_hash

        parsed = urlparse(url)
        path   = parsed.path.lower()
        if any(kw in path for kw in ["admin","staff","manage","superuser","root","control"]):
            self.discovered_admin_urls.add(url)

        return bc


# ─────────────────────────────────────────────
#  DISMISSAL HANDLER
# ─────────────────────────────────────────────

class DismissalHandler:
    """
    Detects and autonomously handles any overlay/popup/modal
    that could block the primary agent mission.
    """

    def __init__(self, driver):
        self.driver = driver

    def clear(self) -> bool:
        dismissed = False
        dismissed |= self._dismiss_alerts()
        dismissed |= self._dismiss_modals()
        dismissed |= self._dismiss_cookie_banners()
        dismissed |= self._dismiss_toasts()
        return dismissed

    def _dismiss_alerts(self) -> bool:
        try:
            alert = self.driver.switch_to.alert
            alert.dismiss()
            return True
        except NoAlertPresentException: return False
        except: return False

    def _dismiss_modals(self) -> bool:
        for sel in DISMISSAL_PATTERNS["selectors"]:
            try:
                btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for btn in btns:
                    if btn.is_displayed() and btn.is_enabled():
                        try: self.driver.execute_script("arguments[0].click();", btn)
                        except: btn.click()
                        time.sleep(0.3)
                        return True
            except: pass
        # Text-based search
        try:
            for btn in self.driver.find_elements(By.CSS_SELECTOR, "button,a,span"):
                try:
                    txt = (btn.text or "").strip().lower()
                    if txt in DISMISSAL_PATTERNS["text"] and btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.3)
                        return True
                except: pass
        except: pass
        return False

    def _dismiss_cookie_banners(self) -> bool:
        for sel in ["#cookie-accept","#cookieConsent .btn","[id*='cookie'] button",
                    "[class*='cookie'] button","[class*='consent'] button"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    self.driver.execute_script("arguments[0].click();", el)
                    return True
            except: pass
        return False

    def _dismiss_toasts(self) -> bool:
        for sel in [".toast-close","[data-notify='dismiss']",".notyf__dismiss",
                    ".alert .close","[class*='notification'] [class*='close']"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    self.driver.execute_script("arguments[0].click();", el)
                    return True
            except: pass
        return False


# ─────────────────────────────────────────────
#  PERFORMANCE AUDITOR
# ─────────────────────────────────────────────

class PerformanceAuditor:
    """
    Extracts Navigation Timing API and Resource Timing API metrics
    from the live browser, grades pages, and detects heavy assets.
    """

    HEAVY_IMG_BYTES   = 1 * 1024 * 1024    # 1 MB
    HEAVY_JS_BYTES    = 500 * 1024          # 500 KB unminified heuristic
    SLOW_TTFB_MS      = 800
    SLOW_LOADED_MS    = 3000

    def __init__(self, driver):
        self.driver = driver
        self.page_metrics: Dict[str, PerformanceMetrics] = {}

    def capture(self, url: str) -> PerformanceMetrics:
        pm = PerformanceMetrics(url=url)
        try:
            timing = self.driver.execute_script("""
                var t = window.performance.timing;
                var nav = window.performance.getEntriesByType('navigation');
                var paint = window.performance.getEntriesByType('paint');
                var fp = 0;
                paint.forEach(function(e){ if(e.name==='first-paint') fp=e.startTime; });
                if(nav.length){
                    return {
                        ttfb: nav[0].responseStart - nav[0].requestStart,
                        dcl:  nav[0].domContentLoadedEventEnd - nav[0].startTime,
                        load: nav[0].loadEventEnd - nav[0].startTime,
                        fp:   fp
                    };
                }
                return {
                    ttfb: t.responseStart - t.fetchStart,
                    dcl:  t.domContentLoadedEventEnd - t.navigationStart,
                    load: t.loadEventEnd - t.navigationStart,
                    fp:   fp
                };""")
            if timing:
                pm.ttfb_ms              = round(max(0, timing.get("ttfb", 0)), 1)
                pm.dom_content_loaded_ms= round(max(0, timing.get("dcl",  0)), 1)
                pm.fully_loaded_ms      = round(max(0, timing.get("load", 0)), 1)
                pm.first_paint_ms       = round(max(0, timing.get("fp",   0)), 1)
        except: pass

        try:
            resources = self.driver.execute_script("""
                return window.performance.getEntriesByType('resource').map(function(r){
                    return {name:r.name, type:r.initiatorType,
                            size:r.transferSize||r.decodedBodySize||0,
                            duration:r.duration};
                });""") or []
            pm.resource_count = len(resources)
            pm.total_transfer_kb = round(sum(r.get("size",0) for r in resources) / 1024, 1)
            for r in resources:
                rtype = r.get("type","")
                rsize = r.get("size", 0)
                rname = r.get("name","")
                is_heavy = False
                reason   = ""
                if rtype == "img" and rsize > self.HEAVY_IMG_BYTES:
                    is_heavy = True; reason = f"Image {rsize//1024}KB"
                elif rtype == "script" and rsize > self.HEAVY_JS_BYTES:
                    is_heavy = True; reason = f"Script {rsize//1024}KB"
                elif rsize > 2 * 1024 * 1024:
                    is_heavy = True; reason = f"Asset {rsize//1024}KB"
                if is_heavy:
                    pm.heavy_resources.append({"url": rname[:120], "size_kb": round(rsize/1024,1),
                                               "type": rtype, "reason": reason,
                                               "duration_ms": round(r.get("duration",0),1)})
        except: pass

        pm.grade = self._grade(pm)
        self.page_metrics[url] = pm
        return pm

    def _grade(self, pm: PerformanceMetrics) -> str:
        score = 100
        if pm.ttfb_ms > self.SLOW_TTFB_MS:      score -= 30
        elif pm.ttfb_ms > 400:                   score -= 15
        if pm.fully_loaded_ms > self.SLOW_LOADED_MS: score -= 30
        elif pm.fully_loaded_ms > 1500:          score -= 15
        score -= min(30, len(pm.heavy_resources) * 10)
        if   score >= 90: return "A"
        elif score >= 75: return "B"
        elif score >= 60: return "C"
        elif score >= 40: return "D"
        else:             return "F"

    def worst_pages(self, n: int = 10) -> List[PerformanceMetrics]:
        return sorted(self.page_metrics.values(),
                      key=lambda p: p.fully_loaded_ms, reverse=True)[:n]


# ─────────────────────────────────────────────
#  HEADER ROTATOR — Headless/Headful Parity
# ─────────────────────────────────────────────

class HeaderRotator:
    """
    Rotates User-Agent and accept headers to simulate real human browsers,
    ensuring headless mode doesn't trigger different security checks.
    """

    def __init__(self):
        self._idx = 0

    def next_ua(self) -> str:
        ua = USER_AGENTS[self._idx % len(USER_AGENTS)]
        self._idx += 1
        return ua

    def patch_driver(self, driver) -> None:
        ua = self.next_ua()
        try:
            driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": ua,
                "acceptLanguage": "en-US,en;q=0.9",
                "platform": "Win32",
            })
        except Exception:
            try: driver.execute_script(f"Object.defineProperty(navigator,'userAgent',{{get:()=>'{ua}'}});")
            except: pass

    def headers_for_requests(self) -> Dict[str, str]:
        return {
            "User-Agent": self.next_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }


# ─────────────────────────────────────────────
#  CONTEXTUAL WRAPPER
# ─────────────────────────────────────────────

class ContextualWrapper:
    """
    Wraps every element interaction in a try-analyze-retry loop.
    Detects obscuring modals and handles them autonomously.
    """

    def __init__(self, driver, dismissal: DismissalHandler):
        self.driver    = driver
        self.dismissal = dismissal

    def click(self, el, retries: int = 3) -> bool:
        for attempt in range(retries):
            try:
                WebDriverWait(self.driver, 3).until(EC.element_to_be_clickable(el))
                el.click()
                return True
            except ElementClickInterceptedException:
                self.dismissal.clear()
                time.sleep(0.4)
            except ElementNotInteractableException:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    self.driver.execute_script("arguments[0].click();", el)
                    return True
                except: pass
            except StaleElementReferenceException:
                return False
            except Exception:
                try: self.driver.execute_script("arguments[0].click();", el)
                except: pass
                if attempt == retries - 1: return False
        return False

    def fill(self, el, value: str) -> bool:
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            tag = (el.get_attribute("tagName") or "").lower()
            if tag == "select":
                try:
                    Select(el).select_by_visible_text(value)
                    return True
                except:
                    try: Select(el).select_by_index(1); return True
                    except: return False
            el.clear()
            el.send_keys(value)
            return True
        except ElementNotInteractableException:
            try:
                self.driver.execute_script(f"arguments[0].value=arguments[1];", el, value)
                return True
            except: return False
        except StaleElementReferenceException: return False
        except Exception: return False

    def navigate(self, url: str, wait_s: float = 2.0) -> bool:
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
            self.dismissal.clear()
            time.sleep(wait_s)
            return True
        except TimeoutException:
            return True
        except Exception:
            return False

    def wait_for_dom_change(self, old_hash: str, timeout: float = 5.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            try:
                body = self.driver.execute_script("return document.body.innerHTML;")
                if hashlib.md5((body or "").encode()).hexdigest() != old_hash:
                    return True
            except: pass
            time.sleep(0.3)
        return False


# ─────────────────────────────────────────────
#  SECURITY PROBE
# ─────────────────────────────────────────────

class SecurityProbe:
    """
    Executes all active security checks:
      - Horizontal & Vertical Privilege Escalation (Force Browsing)
      - Polyglot payload fuzzing across all inputs
      - CSRF entropy analysis
      - IDOR via sequential IDs
      - Header injection, open redirect, path traversal
      - Security headers audit
    """

    def __init__(self, driver, session: requests.Session,
                 base_url: str, rotator: HeaderRotator,
                 perf: PerformanceAuditor, wrapper: ContextualWrapper,
                 logger: logging.Logger, delay: float = 0.3):
        self.driver   = driver
        self.session  = session
        self.base_url = base_url
        self.rotator  = rotator
        self.perf     = perf
        self.wrapper  = wrapper
        self.logger   = logger
        self.delay    = delay
        self.findings: List[SecurityFinding] = []
        self._csrf_tokens_seen: Dict[str, Set[str]] = defaultdict(set)

    def _add(self, sev: str, cat: str, title: str, detail: str = "",
             endpoint: str = "", role: str = "", payload: str = "",
             evidence: str = "") -> None:
        self.findings.append(SecurityFinding(
            severity=sev, category=cat, title=title, detail=detail,
            endpoint=endpoint, role=role, payload=payload, evidence=evidence))

    def _get(self, url: str, cookies: dict = None, timeout: int = 10) -> Optional[requests.Response]:
        try:
            hdrs = self.rotator.headers_for_requests()
            s    = requests.Session()
            s.verify = False
            if cookies:
                for k, v in cookies.items(): s.cookies.set(k, v)
            return s.get(url, headers=hdrs, timeout=timeout, allow_redirects=True)
        except: return None

    def _post(self, url: str, data: dict = None, cookies: dict = None,
              timeout: int = 10) -> Optional[requests.Response]:
        try:
            hdrs = self.rotator.headers_for_requests()
            s    = requests.Session()
            s.verify = False
            if cookies:
                for k, v in cookies.items(): s.cookies.set(k, v)
            return s.post(url, data=data or {}, headers=hdrs, timeout=timeout)
        except: return None

    def _throttle(self): time.sleep(self.delay)

    # ── Force Browsing / Privilege Escalation ──────────────────────────────

    def probe_force_browsing(self, admin_urls: Set[str],
                              low_priv_cookies: Dict[str, dict]) -> None:
        """
        Attempts to access every discovered admin/staff URL using
        lower-privilege session cookies (horizontal + vertical escalation).
        """
        self.logger.info("  [SEC] Force browsing privilege escalation...")
        for url in admin_urls:
            for role_name, cookies in low_priv_cookies.items():
                r = self._get(url, cookies=cookies)
                if not r: continue
                sc = r.status_code
                if sc == 200:
                    body = r.text
                    is_login = any(w in body.lower() for w in
                                   ["login","sign in","password","username","credential"])
                    if not is_login:
                        self._add("CRITICAL","Privilege Escalation",
                                  f"Admin URL accessible by '{role_name}'",
                                  f"URL: {url} Status: {sc}",
                                  endpoint=url, role=role_name,
                                  evidence=body[:150])
                    else:
                        self._add("INFO","Access Control",
                                  f"Admin URL redirects to login for '{role_name}'",
                                  f"URL: {url}",endpoint=url,role=role_name)
                elif sc == 403:
                    self._add("INFO","Access Control",
                              f"Admin URL correctly blocked (403) for '{role_name}'",
                              f"URL: {url}",endpoint=url,role=role_name)
                self._throttle()

    # ── Polyglot Fuzzing ────────────────────────────────────────────────────

    def fuzz_all_inputs(self, role: str = "unknown") -> None:
        """
        Identifies all input fields on the current page (including shadow DOM),
        injects a randomized rotation of polyglot payloads, and analyses responses.
        """
        self.logger.info("  [SEC] Fuzzing all inputs with polyglot payloads...")
        if not self.driver: return
        try:
            inputs = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input:not([type='hidden']):not([type='submit']):not([type='button']),"
                "textarea,[contenteditable='true']")
        except: return

        payload_pool = POLYGLOT_PAYLOADS + XSS_PAYLOADS + SQLI_PAYLOADS
        for el in inputs[:20]:
            try:
                if not el.is_displayed(): continue
                pl = random.choice(payload_pool)
                itype  = (el.get_attribute("type") or "text").lower()
                iname  = el.get_attribute("name") or el.get_attribute("id") or "input"
                if itype in ("email","number","date","tel"): continue

                old_hash = hashlib.md5(
                    (self.driver.execute_script("return document.body.innerHTML;") or "")
                    .encode()).hexdigest()

                self.wrapper.fill(el, pl)
                el.send_keys(Keys.TAB)
                time.sleep(0.3)

                try:
                    src = self.driver.page_source
                except: src = ""

                if pl in src:
                    self._add("HIGH","XSS",f"Polyglot reflected in DOM (field: {iname})",
                              f"Payload: {pl[:60]}",role=role,payload=pl[:80],
                              evidence="Payload found verbatim in page source")

                for ep in SQL_ERROR_PATTERNS:
                    if re.search(ep, src, re.IGNORECASE):
                        self._add("CRITICAL","SQL Injection",
                                  f"SQL error triggered by polyglot (field: {iname})",
                                  f"Payload: {pl[:60]} Pattern: {ep[:30]}",
                                  role=role, payload=pl[:80])
                        break

                for ssti in SSTI_PAYLOADS:
                    if self.wrapper.fill(el, ssti):
                        el.send_keys(Keys.TAB); time.sleep(0.2)
                        try:
                            new_src = self.driver.page_source
                            if "49" in new_src[:5000]:
                                self._add("CRITICAL","SSTI",
                                          f"Template injection: 7*7=49 rendered (field: {iname})",
                                          f"Payload: {ssti}",role=role,payload=ssti)
                        except: pass

                try: el.clear()
                except: pass

            except StaleElementReferenceException: continue
            except Exception: continue
            self._throttle()

    def fuzz_url_params(self, url: str, role: str = "unknown") -> None:
        """Fuzzes URL parameters with path traversal and SQLi payloads."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if not params: return
        for param in list(params.keys())[:5]:
            for pl in (PATH_TRAVERSAL_PAYLOADS[:3] + SQLI_PAYLOADS[:3]):
                new_params = {k: v for k, v in params.items()}
                new_params[param] = [pl]
                fuzz_url = parsed._replace(
                    query=urlencode(new_params, doseq=True)).geturl()
                try:
                    r = self._get(fuzz_url)
                    if not r: continue
                    body = r.text
                    if any(w in body for w in ["root:","[boot loader]","daemon:"]):
                        self._add("CRITICAL","Path Traversal",
                                  f"Path traversal successful via '{param}'",
                                  f"Payload: {pl}",endpoint=fuzz_url,role=role,payload=pl)
                    for ep in SQL_ERROR_PATTERNS:
                        if re.search(ep, body, re.IGNORECASE):
                            self._add("CRITICAL","SQL Injection",
                                      f"SQL error via param '{param}'",
                                      f"Payload: {pl}",endpoint=fuzz_url,role=role,payload=pl)
                            break
                except: pass
                self._throttle()

    # ── CSRF Entropy Analysis ───────────────────────────────────────────────

    def analyse_csrf(self, role: str = "unknown") -> None:
        """
        Inspects all forms for CSRF tokens. If missing or low-entropy
        or non-rotating across requests, flags as Critical.
        """
        self.logger.info("  [SEC] Analysing CSRF tokens...")
        if not self.driver: return
        try:
            forms = self.driver.find_elements(By.TAG_NAME, "form")
        except: return

        for form in forms[:20]:
            try:
                action = form.get_attribute("action") or self.driver.current_url
                method = (form.get_attribute("method") or "GET").upper()
                if method != "POST": continue

                hidden = form.find_elements(By.CSS_SELECTOR, "input[type='hidden']")
                token_found = False
                token_val   = ""
                token_name  = ""

                for h in hidden:
                    n = (h.get_attribute("name") or "").lower()
                    v = h.get_attribute("value") or ""
                    if any(kw in n for kw in ["csrf","token","_token","xsrf","nonce","authenticity"]):
                        token_found = True
                        token_val   = v
                        token_name  = n
                        break

                if not token_found:
                    self._add("CRITICAL","CSRF",
                              f"Form with no CSRF token (action: {action[:60]})",
                              f"Method: {method} Fields: {len(hidden)}",
                              endpoint=action, role=role)
                    continue

                # Entropy check
                entropy = self._shannon_entropy(token_val)
                if entropy < 3.0:
                    self._add("HIGH","CSRF",
                              f"Low-entropy CSRF token (field: {token_name})",
                              f"Entropy: {entropy:.2f} Value: {token_val[:20]}",
                              endpoint=action,role=role,evidence=token_val[:40])

                # Replay / non-rotation check
                prev = self._csrf_tokens_seen[action]
                if token_val and token_val in prev:
                    self._add("HIGH","CSRF",
                              f"CSRF token not rotating across sessions (field: {token_name})",
                              f"Same value seen again on {action[:60]}",
                              endpoint=action,role=role,evidence=token_val[:40])
                if token_val: prev.add(token_val)

            except StaleElementReferenceException: continue
            except Exception: continue

    def _shannon_entropy(self, s: str) -> float:
        if not s: return 0.0
        freq = defaultdict(int)
        for c in s: freq[c] += 1
        l = len(s)
        return -sum((c/l) * math.log2(c/l) for c in freq.values())

    # ── IDOR ────────────────────────────────────────────────────────────────

    def probe_idor(self, api_patterns: List[str], role: str = "unknown") -> None:
        self.logger.info("  [SEC] Probing IDOR...")
        for pattern in api_patterns:
            for tid in [1, 2, 3, 0, -1, 9999, 99999]:
                url = urljoin(self.base_url, pattern.format(id=tid))
                r   = self._get(url)
                if not r: continue
                if r.status_code == 200:
                    try:
                        data = r.json()
                        if data:
                            self._add("HIGH","IDOR",
                                      f"Object accessible via ID={tid}: {pattern}",
                                      f"Status:200 Keys:{list(data.keys())[:4] if isinstance(data,dict) else '[]'}",
                                      endpoint=url,role=role)
                    except: pass
                elif r.status_code == 500:
                    self._add("MEDIUM","Functionality",
                              f"500 error for ID={tid}: {pattern}",
                              f"Server error on invalid ID",endpoint=url,role=role)
                self._throttle()

    # ── Security Headers Audit ──────────────────────────────────────────────

    def audit_security_headers(self, role: str = "unknown") -> None:
        self.logger.info("  [SEC] Auditing security headers...")
        r = self._get(self.base_url)
        if not r: return
        h = {k.lower(): v for k, v in r.headers.items()}

        required = {
            "x-content-type-options":  ("MEDIUM","Missing X-Content-Type-Options"),
            "x-frame-options":         ("MEDIUM","Missing X-Frame-Options (Clickjacking risk)"),
            "x-xss-protection":        ("LOW","Missing X-XSS-Protection header"),
            "strict-transport-security":("HIGH","Missing HSTS header"),
            "content-security-policy": ("HIGH","Missing Content-Security-Policy header"),
            "referrer-policy":         ("LOW","Missing Referrer-Policy"),
            "permissions-policy":      ("LOW","Missing Permissions-Policy"),
        }
        for header, (sev, msg) in required.items():
            if header not in h:
                self._add(sev,"Security Headers",msg,
                          f"Header '{header}' absent from response",role=role)

        csp = h.get("content-security-policy","")
        if csp:
            if "unsafe-inline" in csp:
                self._add("MEDIUM","CSP","CSP allows 'unsafe-inline'",
                          "Weakens XSS protection",role=role,evidence=csp[:80])
            if "unsafe-eval" in csp:
                self._add("MEDIUM","CSP","CSP allows 'unsafe-eval'",
                          "Allows eval() execution",role=role,evidence=csp[:80])
            if "*" in csp:
                self._add("HIGH","CSP","CSP uses wildcard '*'",
                          "Overly permissive policy",role=role,evidence=csp[:80])

        cors = h.get("access-control-allow-origin","")
        if cors == "*":
            self._add("HIGH","CORS","CORS allows all origins (*)",
                      "Any site can make cross-origin requests",role=role)
        elif cors:
            cred = h.get("access-control-allow-credentials","")
            if cred.lower() == "true" and cors != "*":
                self._add("CRITICAL","CORS",
                          "CORS: reflected origin + credentials=true",
                          f"Origin: {cors} Credentials: {cred}",role=role)

    # ── Open Redirect ───────────────────────────────────────────────────────

    def probe_open_redirect(self, role: str = "unknown") -> None:
        for param in ["next","redirect","url","return","returnTo","continue","goto","dest"]:
            url = urljoin(self.base_url, f"/?{param}=https://evil.example.com")
            r   = self._get(url)
            if r and r.status_code in (301,302,303,307,308):
                loc = r.headers.get("location","")
                if "evil.example.com" in loc:
                    self._add("HIGH","Open Redirect",
                              f"Open redirect via '{param}' parameter",
                              f"Redirects to evil.example.com",
                              endpoint=f"/?{param}=",role=role)
            self._throttle()

    # ── Rate Limit ──────────────────────────────────────────────────────────

    def probe_rate_limiting(self, path: str = "/", role: str = "unknown",
                             n: int = 25) -> None:
        url      = urljoin(self.base_url, path)
        statuses = []
        for _ in range(n):
            r = self._get(url)
            if r: statuses.append(r.status_code)
        if 429 not in statuses and 503 not in statuses:
            self._add("MEDIUM","Rate Limiting",
                      f"No rate limiting detected on {path}",
                      f"{n} rapid requests all accepted (statuses: {set(statuses)})",
                      endpoint=path, role=role)

    # ── Information Disclosure ──────────────────────────────────────────────

    def scan_info_disclosure(self, url: str, body: str, role: str = "unknown") -> None:
        patterns = {
            "Stack Trace":   r'(?:Traceback \(most recent call last\)|File "[^"]+", line \d+)',
            "Django Debug":  r'<title>.*?Error.*?Django.*?</title>',
            "PHP Warning":   r'(?:Warning|Notice|Fatal error):\s+\w+',
            "AWS Key":       r'AKIA[0-9A-Z]{16}',
            "JWT Token":     r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}',
            "DB Connection": r'(?:mongodb|mysql|postgres|redis)://[^\s<>"\']{6,}',
            "Private Key":   r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',
            "Internal Path": r'(?:/var/www|/home/\w+|C:\\\\inetpub)',
        }
        for name, pat in patterns.items():
            m = re.search(pat, body[:8000], re.IGNORECASE | re.DOTALL)
            if m:
                self._add("HIGH","Information Disclosure",
                          f"{name} exposed in response",
                          f"Pattern matched at: {m.start()}",
                          endpoint=url, role=role, evidence=m.group(0)[:80])

    # ── HTTP Methods ────────────────────────────────────────────────────────

    def probe_http_methods(self, paths: List[str], role: str = "unknown") -> None:
        for path in paths[:5]:
            url = urljoin(self.base_url, path)
            for method in ["TRACE","OPTIONS","PUT","DELETE"]:
                try:
                    r = self.session.request(method, url, timeout=8, verify=False)
                    if method == "TRACE" and r.status_code == 200:
                        self._add("MEDIUM","HTTP Methods",f"TRACE enabled on {path}",
                                  "Risk: Cross-Site Tracing (XST)",endpoint=path,role=role)
                    elif method == "OPTIONS" and r.status_code == 200:
                        allow = r.headers.get("Allow","")
                        if allow:
                            self._add("INFO","HTTP Methods",f"OPTIONS allowed on {path}",
                                      f"Allow: {allow}",endpoint=path,role=role)
                    elif method in ("PUT","DELETE") and r.status_code in (200,201,204):
                        self._add("HIGH","HTTP Methods",
                                  f"Unrestricted {method} on {path}",
                                  f"Status: {r.status_code}",endpoint=path,role=role)
                except: pass
                self._throttle()


# ─────────────────────────────────────────────
#  UNIVERSAL AUDITOR  — Main Orchestrator
# ─────────────────────────────────────────────

class UniversalAuditor:
    """
    Graph-based autonomous agent.
    Drives all sub-components in coordinated phases:
      1. Pre-auth recon + security headers
      2. Semantic page mapping & performance capture
      3. Per-role login → graph navigation → security probing
      4. Cross-role force browsing escalation
      5. Report generation
    """

    VERSION = "2.0"

    IDOR_PATTERNS = [
        "/api/students/{id}/", "/api/teachers/{id}/", "/api/courses/{id}/",
        "/api/student-finances/{id}/", "/api/student-schedules/{id}/",
        "/api/academic-terms/{id}/", "/api/academic-history/{id}/",
        "/api/subjects/{id}/", "/api/users/{id}/",
    ]

    def __init__(self, base_url: str, roles_config: List[Dict],
                 headless: bool = False, browser: str = "chrome",
                 skip_destructive: bool = False, delay: float = 0.5,
                 output_dir: str = "audit_results", roles_filter: List[str] = None,
                 pattern_path: Optional[str] = None, visual_debug: bool = False):

        self.base_url         = base_url.rstrip("/")
        self.roles_config     = roles_config
        self.headless         = headless
        self.browser          = browser.lower()
        self.skip_destructive = skip_destructive
        self.delay            = delay
        self.output_dir       = output_dir
        self.roles_filter     = [r.lower() for r in roles_filter] if roles_filter else None
        self.pattern_path     = pattern_path
        self.visual_debug     = visual_debug

        os.makedirs(self.output_dir, exist_ok=True)

        self.logger  = self._build_logger()
        self.rotator = HeaderRotator()
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(self.rotator.headers_for_requests())

        self.driver: Optional[webdriver.Remote] = None
        self.mapper:    Optional[SemanticMapper]   = None
        self.tracker:   Optional[StateTracker]     = None
        self.dismissal: Optional[DismissalHandler] = None
        self.wrapper:   Optional[ContextualWrapper]= None
        self.perf:      Optional[PerformanceAuditor] = None
        self.probe:     Optional[SecurityProbe]    = None
        self.ui_ctrl:   Optional["UIControlDriver"] = None

        self.findings:     List[SecurityFinding] = []
        self.results:      List[TestResult]      = []
        self.graph:        Dict[str, List[str]]  = defaultdict(list)  # url -> [child urls]
        self.role_cookies: Dict[str, dict]       = {}   # role_name -> cookies dict
        self.start_time:   Optional[datetime]    = None
        self.end_time:     Optional[datetime]    = None

    # ── Logger ─────────────────────────────────────────────────────────────

    def _build_logger(self) -> logging.Logger:
        log = logging.getLogger("UniversalAuditor")
        log.setLevel(logging.DEBUG)
        log.handlers.clear()
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        ch  = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO); ch.setFormatter(fmt); log.addHandler(ch)
        fh  = logging.FileHandler(os.path.join(self.output_dir, "audit.log"), encoding="utf-8")
        fh.setLevel(logging.DEBUG); fh.setFormatter(fmt); log.addHandler(fh)
        return log

    # ── Driver Initialisation ───────────────────────────────────────────────

    def _init_driver(self) -> None:
        if not SELENIUM_OK:
            raise RuntimeError("selenium package not installed")
        for browser in [self.browser, "chrome", "firefox"]:
            try:
                self.driver = self._launch(browser)
                self.browser = browser
                self.logger.info(f"Browser: {browser} launched OK")
                break
            except Exception as exc:
                self.logger.warning(f"Browser '{browser}' failed: {exc}")

        if not self.driver:
            raise RuntimeError("No browser could be launched")

        self.rotator.patch_driver(self.driver)
        self.dismissal = DismissalHandler(self.driver)
        self.mapper    = SemanticMapper(self.driver)
        self.tracker   = StateTracker(self.driver)
        self.wrapper   = ContextualWrapper(self.driver, self.dismissal)
        self.perf      = PerformanceAuditor(self.driver)
        self.probe     = SecurityProbe(
            self.driver, self.session, self.base_url,
            self.rotator, self.perf, self.wrapper,
            self.logger, self.delay)

        if UICTRL_OK:
            self.ui_ctrl = UIControlDriver(
                driver        = self.driver,
                pattern_path  = self.pattern_path,
                visual_debug  = self.visual_debug,
                debug_dir     = os.path.join(self.output_dir, "ui_debug"),
                logger        = self.logger,
            )
        else:
            self.logger.warning("[Auditor] ui_control_driver.py not found — using legacy login")

    def _launch(self, browser: str):
        if browser == "chrome":
            opts = ChromeOptions()
            if self.headless: opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox"); opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            opts.add_argument("--window-size=1366,768")
            if WDM_OK:
                return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)
            return webdriver.Chrome(options=opts)

        elif browser == "firefox":
            opts = FirefoxOptions()
            if self.headless: opts.add_argument("--headless")
            opts.set_preference("general.useragent.override", self.rotator.next_ua())
            if WDM_OK:
                return webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=opts)
            return webdriver.Firefox(options=opts)

        elif browser == "edge":
            opts = EdgeOptions()
            if self.headless: opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            if WDM_OK:
                return webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=opts)
            return webdriver.Edge(options=opts)

        raise ValueError(f"Unknown browser: {browser}")

    # ── Safe Execution ──────────────────────────────────────────────────────

    def _safe(self, name: str, fn, *args, **kwargs):
        start = time.time()
        try:
            result = fn(*args, **kwargs)
            self.results.append(TestResult(name, "PASSED", "OK",
                                           duration=time.time()-start))
            return result
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            self.logger.error(f"[ERROR] {name}: {exc}")
            self.results.append(TestResult(name, "ERROR", str(exc)[:200],
                                           duration=time.time()-start))
            return None

    def _throttle(self): time.sleep(self.delay)

    # ── Session Cookie Capture ──────────────────────────────────────────────

    def _harvest_cookies(self) -> dict:
        try:
            return {c["name"]: c["value"] for c in self.driver.get_cookies()}
        except: return {}

    # ── Semantic Login (pattern-driven with heuristic fallback) ────────────

    def _semantic_login(self, credentials: dict) -> bool:
        login_url = urljoin(self.base_url, credentials.get("login_path", "/"))
        username  = credentials.get("username", "")
        password  = credentials.get("password", "")

        if not username or not password:
            self.logger.warning("  No credentials provided — skipping login")
            return False

        self.wrapper.navigate(login_url)
        self.dismissal.clear()

        # ── Path A: UIControlDriver (pattern-driven, resilient) ───────────
        if self.ui_ctrl:
            self.logger.info("  [Login] Using UIControlDriver (pattern-driven)")
            ok = self.ui_ctrl.execute_login(
                username  = username,
                password  = password,
                login_url = None,  # already navigated above
            )
            self.ui_ctrl.restore_main_frame()
            if ok:
                self.dismissal.clear()
                return True
            self.logger.warning("  [Login] UIControlDriver failed — falling back to legacy heuristic")

        # ── Path B: Legacy heuristic (no pattern file) ────────────────────
        self.logger.info("  [Login] Using legacy heuristic finder")
        user_el = self._find_credential_field(["username", "email", "user", "login", "id"])
        pass_el = self._find_credential_field(["password", "pass", "pwd", "secret"])

        if not user_el or not pass_el:
            self.logger.warning("  [Login] Could not locate credential fields")
            return False

        self.wrapper.fill(user_el, username)
        self.wrapper.fill(pass_el, password)

        submit  = self._find_submit()
        old_url = self.driver.current_url
        if submit:
            self.wrapper.click(submit)
        else:
            try:
                pass_el.send_keys(Keys.RETURN)
            except Exception:
                return False

        time.sleep(2)
        self.dismissal.clear()
        return self.driver.current_url != old_url

    def _find_credential_field(self, hints: List[str]):
        for hint in hints:
            for attr in ["name", "id", "placeholder", "autocomplete", "aria-label"]:
                try:
                    el = self.driver.find_element(
                        By.CSS_SELECTOR,
                        f"input[{attr}*='{hint}' i]:not([type='hidden'])")
                    if el.is_displayed():
                        return el
                except Exception:
                    pass
        for itype in ["text", "email"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, f"input[type='{itype}']")
                if el.is_displayed():
                    return el
            except Exception:
                pass
        return None

    def _find_submit(self):
        for sel in ["input[type='submit']", "button[type='submit']",
                    "button[aria-label*='login' i]", "button[aria-label*='sign in' i]"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    return el
            except Exception:
                pass
        try:
            for btn in self.driver.find_elements(By.TAG_NAME, "button"):
                if (btn.text or "").strip().lower() in ("login", "log in", "sign in",
                                                         "submit", "enter", "go"):
                    return btn
        except Exception:
            pass
        return None

    # ── Graph-Based Page Exploration ────────────────────────────────────────

    def _explore_graph(self, start_url: str, role: str, max_pages: int = 60) -> None:
        queue   = deque([start_url])
        visited: Set[str] = set()

        while queue and len(visited) < max_pages:
            url = queue.popleft()
            if url in visited: continue
            if urlparse(url).netloc != urlparse(self.base_url).netloc: continue
            visited.add(url)

            self.logger.info(f"  [GRAPH] Visiting: {url[:80]} (role={role})")
            ok = self.wrapper.navigate(url, wait_s=1.0)
            if not ok: continue

            self.dismissal.clear()
            state = self.tracker.snapshot(role)
            pm    = self.perf.capture(url)

            nodes   = self.mapper.map_page()
            nav_els = [n for n in nodes if n.node_type == NodeType.NAVIGATION and n.href]

            # Correlate slow page with security surface
            is_slow = pm.fully_loaded_ms > PerformanceAuditor.SLOW_LOADED_MS
            if is_slow and pm.fully_loaded_ms > 0:
                self._add_finding(SecurityFinding(
                    severity="LOW", category="Performance",
                    title=f"Slow page load: {urlparse(url).path or '/'}",
                    detail=f"Loaded:{pm.fully_loaded_ms}ms TTFB:{pm.ttfb_ms}ms Grade:{pm.grade}",
                    endpoint=url, role=role, perf_correlated=True, perf_ms=pm.fully_loaded_ms))

            # Scan for info disclosure in live page source
            try:
                self.probe.scan_info_disclosure(url, self.driver.page_source[:10000], role)
            except: pass

            # Fuzz URL params on this page
            self._safe(f"fuzz-params-{urlparse(url).path[:30]}", self.probe.fuzz_url_params, url, role)

            # Fuzz inputs on this page
            self._safe(f"fuzz-inputs-{urlparse(url).path[:30]}", self.probe.fuzz_all_inputs, role)

            # CSRF analysis
            self._safe(f"csrf-{urlparse(url).path[:30]}", self.probe.analyse_csrf, role)

            # Enqueue discovered links
            for node in nav_els[:20]:
                child = node.href
                if child and child not in visited and child not in queue:
                    if self.base_url in child or child.startswith("/"):
                        if child.startswith("/"):
                            child = urljoin(self.base_url, child)
                        self.graph[url].append(child)
                        queue.append(child)

            self._throttle()

    def _add_finding(self, f: SecurityFinding) -> None:
        self.findings.append(f)

    # ── Main Run ────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.start_time = datetime.now()
        self.logger.info("=" * 70)
        self.logger.info(f"  Universal Web Auditor v{self.VERSION}")
        self.logger.info(f"  Target : {self.base_url}")
        self.logger.info(f"  Browser: {self.browser}  Headless: {self.headless}")
        self.logger.info(f"  Platform: {platform.system()} {platform.release()}")
        self.logger.info(f"  Started: {self.start_time:%Y-%m-%d %H:%M:%S}")
        self.logger.info("=" * 70)

        try:
            self._init_driver()
        except Exception as e:
            self.logger.critical(f"Browser init failed: {e}")
            self.end_time = datetime.now()
            self._generate_report()
            return

        # ── Phase 1: Pre-auth Recon ────────────────────────────────────────
        self.logger.info("\n── Phase 1: Pre-Auth Recon ──")
        self._safe("security-headers", self.probe.audit_security_headers, "unauthenticated")
        self._safe("open-redirect",    self.probe.probe_open_redirect,    "unauthenticated")
        self._safe("rate-limit-root",  self.probe.probe_rate_limiting,    "/", "unauthenticated")
        self._safe("http-methods",     self.probe.probe_http_methods,
                   ["/", "/api/students/", "/api/courses/"], "unauthenticated")
        self._safe("idor-unauth",      self.probe.probe_idor,
                   self.IDOR_PATTERNS, "unauthenticated")

        # ── Phase 2: Pre-auth graph walk ───────────────────────────────────
        self.logger.info("\n── Phase 2: Unauthenticated Graph Walk ──")
        self._safe("graph-unauth", self._explore_graph,
                   self.base_url, "unauthenticated", max_pages=15)

        # ── Phase 3: Per-Role Testing ──────────────────────────────────────
        roles = self.roles_config
        if self.roles_filter:
            roles = [r for r in roles if
                     r.get("name","").lower() in self.roles_filter or
                     r.get("slug","").lower() in self.roles_filter]

        for role_cfg in roles:
            rname = role_cfg.get("name", role_cfg.get("slug","unknown"))
            creds = role_cfg.get("credentials", {})

            self.logger.info(f"\n── Phase 3: Role '{rname}' ──")

            logged_in = self._safe(f"login-{rname}", self._semantic_login, creds)
            if not logged_in:
                self.logger.warning(f"  Login failed for '{rname}', skipping authenticated tests")
                continue

            self.role_cookies[rname] = self._harvest_cookies()
            dashboard = creds.get("dashboard_path", "/")

            self._safe(f"graph-{rname}", self._explore_graph,
                       urljoin(self.base_url, dashboard), rname, max_pages=40)

            self._safe(f"idor-{rname}", self.probe.probe_idor, self.IDOR_PATTERNS, rname)
            self._safe(f"rate-limit-{rname}", self.probe.probe_rate_limiting, "/", rname)
            self._safe(f"http-methods-{rname}", self.probe.probe_http_methods,
                       ["/", "/api/students/", "/api/courses/"], rname)

            # Rotate UA mid-session to check headful/headless parity
            self.rotator.patch_driver(self.driver)
            self._throttle()

            # Logout heuristically
            self._safe(f"logout-{rname}", self._semantic_logout)

        # ── Phase 4: Force Browsing (cross-role) ───────────────────────────
        if len(self.role_cookies) >= 2 and self.tracker.discovered_admin_urls:
            self.logger.info("\n── Phase 4: Cross-Role Force Browsing ──")
            # Build low-privilege cookie set (all non-admin roles)
            low_priv = {rn: ck for rn, ck in self.role_cookies.items()
                        if not any(w in rn.lower() for w in ["admin","super","director","head"])}
            if low_priv:
                self._safe("force-browsing", self.probe.probe_force_browsing,
                           self.tracker.discovered_admin_urls, low_priv)

        # Collect probe findings
        for f in self.probe.findings:
            self.findings.append(f)

        # ── Phase 5: Report ────────────────────────────────────────────────
        self.end_time = datetime.now()
        try:
            if self.driver: self.driver.quit()
        except: pass

        self.logger.info("\n── Phase 5: Generating Report ──")
        self._generate_report()

    # ── Semantic Logout ─────────────────────────────────────────────────────

    def _semantic_logout(self) -> None:
        nodes = self.mapper.map_page()
        acct  = [n for n in nodes if n.node_type == NodeType.ACCOUNT_MGMT]
        for n in acct:
            if any(w in n.label.lower() for w in ["logout","log out","sign out"]):
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, n.selector)
                    self.wrapper.click(el); time.sleep(1.5)
                    return
                except: pass
        # Fallback: direct URL
        for path in ["/logout/","/accounts/logout/","/auth/logout/","/signout/"]:
            try:
                self.wrapper.navigate(urljoin(self.base_url, path), wait_s=1.0)
                return
            except: pass

    # ── Report Generation ───────────────────────────────────────────────────

    def _generate_report(self) -> None:
        duration = ((self.end_time - self.start_time).total_seconds()
                    if self.start_time and self.end_time else 0)

        sev_counts  = defaultdict(int)
        cat_counts  = defaultdict(int)
        stat_counts = defaultdict(int)
        for f in self.findings:
            sev_counts[f.severity]  += 1
            cat_counts[f.category]  += 1
        for r in self.results:
            stat_counts[r.status]   += 1

        worst_perf = []
        if self.perf:
            worst_perf = [asdict(p) for p in self.perf.worst_pages(10)]

        # Correlate: mark findings whose endpoint is a slow page
        slow_urls = {p["url"] for p in worst_perf if p.get("fully_loaded_ms",0) > 1500}
        for f in self.findings:
            if f.endpoint in slow_urls and not f.perf_correlated:
                f.perf_correlated = True
                pm = self.perf.page_metrics.get(f.endpoint)
                if pm: f.perf_ms = pm.fully_loaded_ms

        nav_graph_edges = sum(len(v) for v in self.graph.values())

        report = {
            "meta": {
                "tool": "Universal Web Security & Performance Auditor",
                "version": self.VERSION,
                "target": self.base_url,
                "browser": self.browser,
                "platform": f"{platform.system()} {platform.release()}",
                "start_time": self.start_time.isoformat() if self.start_time else "",
                "end_time":   self.end_time.isoformat()   if self.end_time   else "",
                "duration_seconds": round(duration, 2),
                "headless": self.headless,
            },
            "summary": {
                "total_findings":    len(self.findings),
                "critical":          sev_counts.get("CRITICAL", 0),
                "high":              sev_counts.get("HIGH",     0),
                "medium":            sev_counts.get("MEDIUM",   0),
                "low":               sev_counts.get("LOW",      0),
                "info":              sev_counts.get("INFO",     0),
                "total_tests":       len(self.results),
                "passed":            stat_counts.get("PASSED",  0),
                "errors":            stat_counts.get("ERROR",   0),
                "pages_visited":     len(self.tracker.visited_urls) if self.tracker else 0,
                "admin_urls_found":  len(self.tracker.discovered_admin_urls) if self.tracker else 0,
                "graph_edges":       nav_graph_edges,
                "roles_tested":      list(self.role_cookies.keys()),
                "perf_pages_graded": len(self.perf.page_metrics) if self.perf else 0,
            },
            "findings_by_category": dict(cat_counts),
            "findings":             [asdict(f) for f in self.findings],
            "test_results":         [asdict(r) for r in self.results],
            "performance": {
                "worst_pages":  worst_perf,
                "all_pages":    [asdict(p) for p in self.perf.page_metrics.values()] if self.perf else [],
            },
            "navigation_graph":     dict(self.graph),
            "admin_urls_discovered": list(self.tracker.discovered_admin_urls) if self.tracker else [],
        }

        os.makedirs(self.output_dir, exist_ok=True)

        json_path = os.path.join(self.output_dir, "audit_report.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=str)

        html_path = os.path.join(self.output_dir, "audit_report.html")
        self._write_html(report, html_path)

        self.logger.info("\n" + "=" * 70)
        self.logger.info("  AUDIT COMPLETE")
        self.logger.info("=" * 70)
        self.logger.info(f"  Duration : {duration:.1f}s")
        self.logger.info(f"  Pages    : {report['summary']['pages_visited']}  "
                         f"Admin URLs: {report['summary']['admin_urls_found']}")
        self.logger.info(f"  Findings : {len(self.findings)}  "
                         f"CRITICAL:{sev_counts.get('CRITICAL',0)}  "
                         f"HIGH:{sev_counts.get('HIGH',0)}  "
                         f"MEDIUM:{sev_counts.get('MEDIUM',0)}")
        self.logger.info(f"  JSON     : {json_path}")
        self.logger.info(f"  HTML     : {html_path}")
        self.logger.info("=" * 70)

    def _write_html(self, data: dict, path: str) -> None:
        s   = data["summary"]
        m   = data["meta"]
        SEV = {"CRITICAL":"#e63946","HIGH":"#f4a261","MEDIUM":"#e9c46a",
               "LOW":"#2a9d8f","INFO":"#6c757d"}
        STA = {"PASSED":"#2a9d8f","FAILED":"#e63946","ERROR":"#f4a261",
               "WARNING":"#e9c46a","SKIPPED":"#6c757d"}

        worst_rows = ""
        for p in data["performance"].get("worst_pages", []):
            grade_color = {"A":"#2a9d8f","B":"#57cc99","C":"#e9c46a","D":"#f4a261","F":"#e63946"}.get(p.get("grade","?"),"#888")
            worst_rows += (f"<tr><td class='ep'>{p['url'][:70]}</td>"
                           f"<td>{p.get('ttfb_ms',0):.0f}ms</td>"
                           f"<td>{p.get('dom_content_loaded_ms',0):.0f}ms</td>"
                           f"<td>{p.get('fully_loaded_ms',0):.0f}ms</td>"
                           f"<td>{p.get('first_paint_ms',0):.0f}ms</td>"
                           f"<td>{p.get('resource_count',0)}</td>"
                           f"<td>{p.get('total_transfer_kb',0):.1f} KB</td>"
                           f"<td><b style='color:{grade_color}'>{p.get('grade','?')}</b></td></tr>\n")

        finding_rows = ""
        for f in data["findings"]:
            color = SEV.get(f["severity"],"#888")
            perf_badge = ('<span style="background:#e9c46a;color:#333;border-radius:4px;'
                          f'padding:2px 6px;font-size:0.75em;margin-left:6px">⚡ {f.get("perf_ms",0):.0f}ms</span>'
                          if f.get("perf_correlated") else "")
            finding_rows += (f"<tr data-sev='{f['severity']}'>"
                             f"<td><span class='badge' style='background:{color}'>{f['severity']}</span>{perf_badge}</td>"
                             f"<td>{html.escape(f['category'])}</td>"
                             f"<td>{html.escape(f['title'][:80])}</td>"
                             f"<td class='detail'>{html.escape(f.get('detail','')[:100])}</td>"
                             f"<td class='ep'>{html.escape(f.get('endpoint','')[:55])}</td>"
                             f"<td>{html.escape(f.get('role',''))}</td>"
                             f"<td class='detail'>{html.escape(f.get('evidence','')[:60])}</td></tr>\n")

        result_rows = ""
        for r in data["test_results"]:
            color = STA.get(r["status"],"#888")
            result_rows += (f"<tr><td>{html.escape(r['test_name'][:55])}</td>"
                            f"<td><span class='badge' style='background:{color}'>{r['status']}</span></td>"
                            f"<td class='detail'>{html.escape(r['message'][:80])}</td>"
                            f"<td>{r['duration']:.2f}s</td></tr>\n")

        admin_urls = "\n".join(f"<li class='ep'>{html.escape(u)}</li>"
                               for u in data.get("admin_urls_discovered",[]))

        cat_cards = ""
        for cat, cnt in sorted(data.get("findings_by_category",{}).items(), key=lambda x:-x[1]):
            cat_cards += (f"<div class='card'><div class='num' style='color:#e63946'>{cnt}</div>"
                          f"<div class='lbl'>{html.escape(cat)}</div></div>\n")

        html_out = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Web Audit — {html.escape(m['target'])}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:#0d1117;color:#c9d1d9;line-height:1.6;font-size:14px}}
.container{{max-width:1280px;margin:0 auto;padding:24px}}
h1{{color:#58a6ff;font-size:1.6em;margin-bottom:4px}}
h2{{color:#58a6ff;font-size:1.15em;margin:32px 0 12px;border-bottom:1px solid #21262d;padding-bottom:6px}}
.meta{{color:#8b949e;font-size:0.85em;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0}}
.card{{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:16px;text-align:center}}
.num{{font-size:2em;font-weight:700}}
.lbl{{font-size:0.78em;color:#8b949e;margin-top:4px}}
table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:0.87em}}
th{{background:#161b22;padding:10px 12px;text-align:left;font-weight:600;color:#8b949e;position:sticky;top:0}}
td{{padding:8px 12px;border-bottom:1px solid #21262d}}
tr:hover{{background:#161b22}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:0.78em;font-weight:600;color:#fff}}
.detail{{max-width:320px;word-break:break-word;color:#8b949e}}
.ep{{font-family:monospace;font-size:0.82em;color:#58a6ff;word-break:break-all}}
.filter-bar{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}}
.fbtn{{padding:5px 12px;border:1px solid #21262d;background:#161b22;color:#c9d1d9;
       border-radius:6px;cursor:pointer;font-size:0.82em}}
.fbtn:hover,.fbtn.on{{background:#21262d;color:#58a6ff;border-color:#58a6ff}}
ul{{list-style:none;padding:0}}li{{padding:2px 0}}
</style></head><body><div class="container">
<h1>Universal Web Security &amp; Performance Audit</h1>
<p class="meta">Target: <b>{html.escape(m['target'])}</b> &nbsp;|&nbsp;
Browser: {html.escape(m['browser'])} &nbsp;|&nbsp;
Platform: {html.escape(m['platform'])} &nbsp;|&nbsp;
Duration: {m['duration_seconds']}s &nbsp;|&nbsp;
{m.get('start_time','')[:19]}</p>

<h2>Overview</h2>
<div class="grid">
<div class="card"><div class="num" style="color:#e63946">{s['critical']}</div><div class="lbl">Critical</div></div>
<div class="card"><div class="num" style="color:#f4a261">{s['high']}</div><div class="lbl">High</div></div>
<div class="card"><div class="num" style="color:#e9c46a">{s['medium']}</div><div class="lbl">Medium</div></div>
<div class="card"><div class="num" style="color:#2a9d8f">{s['low']}</div><div class="lbl">Low</div></div>
<div class="card"><div class="num" style="color:#58a6ff">{s['total_findings']}</div><div class="lbl">Total Findings</div></div>
<div class="card"><div class="num" style="color:#58a6ff">{s['pages_visited']}</div><div class="lbl">Pages Visited</div></div>
<div class="card"><div class="num" style="color:#e63946">{s['admin_urls_found']}</div><div class="lbl">Admin URLs Found</div></div>
<div class="card"><div class="num" style="color:#f4a261">{s['perf_pages_graded']}</div><div class="lbl">Pages Graded</div></div>
</div>

<h2>Findings by Category</h2>
<div class="grid">{cat_cards}</div>

<h2>Security Findings ({s['total_findings']})</h2>
<div class="filter-bar">
<button class="fbtn on" onclick="flt(this,'all')">All</button>
<button class="fbtn" onclick="flt(this,'CRITICAL')">Critical ({s['critical']})</button>
<button class="fbtn" onclick="flt(this,'HIGH')">High ({s['high']})</button>
<button class="fbtn" onclick="flt(this,'MEDIUM')">Medium ({s['medium']})</button>
<button class="fbtn" onclick="flt(this,'LOW')">Low ({s['low']})</button>
<button class="fbtn" onclick="flt(this,'perf')">⚡ Perf-Correlated</button>
</div>
<table id="ftbl">
<tr><th>Severity</th><th>Category</th><th>Title</th><th>Detail</th><th>Endpoint</th><th>Role</th><th>Evidence</th></tr>
{finding_rows}
</table>

<h2>Performance — Worst Pages (Fully Loaded)</h2>
<table>
<tr><th>URL</th><th>TTFB</th><th>DCL</th><th>Loaded</th><th>First Paint</th><th>Resources</th><th>Transfer</th><th>Grade</th></tr>
{worst_rows}
</table>

<h2>Discovered Admin / Privileged URLs ({len(data.get('admin_urls_discovered',[]))})</h2>
<ul>{admin_urls}</ul>

<h2>Test Execution Log ({len(data['test_results'])})</h2>
<table>
<tr><th>Test</th><th>Status</th><th>Message</th><th>Duration</th></tr>
{result_rows}
</table>

</div>
<script>
function flt(btn,sev){{
  document.querySelectorAll('.fbtn').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  document.querySelectorAll('#ftbl tr[data-sev]').forEach(row=>{{
    if(sev==='all') row.style.display='';
    else if(sev==='perf') row.style.display=row.querySelector('.badge+span')?'':'none';
    else row.style.display=row.dataset.sev===sev?'':'none';
  }});
}}
</script>
</body></html>"""
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html_out)


# ─────────────────────────────────────────────
#  ROLES CONFIG LOADER
# ─────────────────────────────────────────────

def load_roles_config(config_path: Optional[str]) -> List[Dict]:
    """
    Loads roles from rms_test_config.json if present, otherwise returns
    a minimal set of generic roles to attempt.
    """
    candidates = [
        config_path,
        os.path.join(os.path.dirname(__file__), "rms_test_config.json"),
        "rms_test_config.json",
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    cfg = json.load(fh)
                roles = cfg.get("roles", [])
                if roles:
                    return roles
            except Exception:
                pass
    return [
        {"name": "admin",   "slug": "admin",
         "credentials": {"username": "", "password": "", "login_path": "/", "dashboard_path": "/"}},
        {"name": "student", "slug": "student",
         "credentials": {"username": "", "password": "", "login_path": "/", "dashboard_path": "/"}},
    ]


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Universal Web Security & Performance Auditor v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python rms_autonomous_agent.py --url http://localhost:8000
  python rms_autonomous_agent.py --url http://localhost:8000 --headless
  python rms_autonomous_agent.py --url http://localhost:8000 --roles admin,teacher --browser firefox
  python rms_autonomous_agent.py --url http://localhost:8000 --skip-destructive --delay 1.0
  python rms_autonomous_agent.py --url http://localhost:8000 --config rms_test_config.json --output ./reports
""")
    parser.add_argument("--url",              required=True,
                        help="Target base URL (e.g. http://localhost:8000)")
    parser.add_argument("--config",           default=None,
                        help="Path to roles config JSON (default: rms_test_config.json)")
    parser.add_argument("--headless",         action="store_true",
                        help="Run browser headlessly")
    parser.add_argument("--browser",          default="chrome",
                        choices=["chrome","firefox","edge"],
                        help="Browser driver (default: chrome)")
    parser.add_argument("--roles",            default=None,
                        help="Comma-separated role names/slugs to test (default: all)")
    parser.add_argument("--skip-destructive", action="store_true",
                        help="Skip destructive write/delete operations")
    parser.add_argument("--delay",            type=float, default=0.5,
                        help="Seconds between requests (default: 0.5)")
    parser.add_argument("--output",           default="audit_results",
                        help="Output directory for reports (default: audit_results)")
    parser.add_argument("--max-pages",        type=int,   default=60,
                        help="Maximum pages to crawl per role (default: 60)")
    parser.add_argument("--pattern",           default=None,
                        help="Path to ui_pattern.json recorded by rms_pattern_recorder.py")
    parser.add_argument("--visual-debug",      action="store_true",
                        help="Highlight each element with a red border while interacting")

    args         = parser.parse_args()
    roles_filter = [r.strip() for r in args.roles.split(",")] if args.roles else None
    roles_config = load_roles_config(args.config)

    auditor = UniversalAuditor(
        base_url         = args.url,
        roles_config     = roles_config,
        headless         = args.headless,
        browser          = args.browser,
        skip_destructive = args.skip_destructive,
        delay            = args.delay,
        output_dir       = args.output,
        roles_filter     = roles_filter,
        pattern_path     = args.pattern,
        visual_debug     = args.visual_debug,
    )
    auditor.run()


if __name__ == "__main__":
    main()
