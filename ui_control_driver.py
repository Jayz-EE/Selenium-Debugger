#!/usr/bin/env python3
"""
UIControlDriver v1.0
Resilient Selenium UI interaction engine that ingests ui_pattern.json.

Features:
  - Fuzzy Finder   : ID → Name → Placeholder → CSS Selector → XPath
  - Smart IFrames  : scans all iframes before failing
  - Human Mimicry  : recorded latency + Tab-key navigation between fields
  - Self-Healing   : screenshot + DOM snapshot on every failure
  - Visual Debugger: draws a red outline on the element being interacted with
  - Stale Recovery : retries every action up to STALE_RETRIES times
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import Select
    from selenium.common.exceptions import (
        ElementNotInteractableException,
        InvalidSwitchToTargetException,
        NoSuchElementException,
        NoSuchFrameException,
        StaleElementReferenceException,
    )
except ImportError:
    raise ImportError("Selenium is required.  Run: pip install selenium")

# ─────────────────────────────────────────────────────────────────────────────
#  JS snippets
# ─────────────────────────────────────────────────────────────────────────────

_JS_HIGHLIGHT = (
    "arguments[0].style.outline='3px solid red';"
    "arguments[0].style.boxShadow='0 0 8px 4px rgba(255,0,0,0.65)';"
    "arguments[0].style.transition='outline 0.1s';"
)
_JS_UNHIGHLIGHT = (
    "arguments[0].style.outline='';"
    "arguments[0].style.boxShadow='';"
)
_JS_FILL = (
    "arguments[0].value = arguments[1];"
    "arguments[0].dispatchEvent(new Event('input',  {bubbles:true}));"
    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));"
)


# ─────────────────────────────────────────────────────────────────────────────
#  UIControlDriver
# ─────────────────────────────────────────────────────────────────────────────

class UIControlDriver:
    """
    Drop-in replacement / augmentation for direct Selenium element interactions.
    Instantiate once per browser session and call ``execute_login`` or
    ``fuzzy_find`` / ``human_fill`` / ``human_click`` individually.
    """

    STALE_RETRIES  = 3
    # No per-strategy timeout — strategies use instant find_elements (no hang)

    def __init__(
        self,
        driver,
        pattern_path:  Optional[str]            = None,
        visual_debug:  bool                     = False,
        debug_dir:     str                      = "ui_debug",
        logger:        Optional[logging.Logger] = None,
    ) -> None:
        self.driver       = driver
        self.visual_debug = visual_debug
        self.debug_dir    = debug_dir
        self.logger       = logger or logging.getLogger("UIControlDriver")
        self.pattern      = self._load_pattern(pattern_path)
        self._iframe_ctx: Optional[int] = None   # index of active iframe, or None

    # ── Pattern loading ───────────────────────────────────────────────────────

    def _load_pattern(self, path: Optional[str]) -> Optional[Dict]:
        candidates = [path] if path else []
        candidates += [
            "ui_pattern.json",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_pattern.json"),
        ]
        for p in candidates:
            if p and os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8") as fh:
                        data = json.load(fh)
                    self.logger.info(
                        f"[UICtrl] Loaded pattern: {p}  "
                        f"({data['meta'].get('total_events','?')} events)"
                    )
                    return data
                except Exception as e:
                    self.logger.warning(f"[UICtrl] Cannot load pattern {p}: {e}")
        self.logger.debug("[UICtrl] No ui_pattern.json found — heuristic-only mode")
        return None

    def get_field_pattern(self, data_type: str,
                           page_url: Optional[str] = None) -> Optional[Dict]:
        """
        Return the recorded field pattern for a given data_type string.
        When page_url is provided, prefer fields whose recorded URL path
        matches the current page — avoids pulling fields from other pages
        that were recorded in the same session.
        """
        if not self.pattern:
            return None
        fields = self.pattern.get("session_summary", {}).get("fields", {})

        # Normalise the current page path for comparison
        cur_path = ""
        if page_url:
            try:
                from urllib.parse import urlparse
                cur_path = urlparse(page_url).path.rstrip("/")
            except Exception:
                pass

        best: Optional[Dict] = None
        for _k, fdata in fields.items():
            dt  = fdata.get("data_type", "").lower()
            pwd = fdata.get("is_password", False)
            matched_type = (dt == data_type.lower()) or \
                           (pwd and data_type.lower() == "password") or \
                           (dt == "email" and data_type.lower() in ("username", "email"))
            if not matched_type:
                continue

            # If we have a URL hint, prefer fields recorded on the same page
            if cur_path:
                rec_url = fdata.get("meta", {}).get("url", "") or \
                          self._find_field_url_from_events(fdata)
                try:
                    from urllib.parse import urlparse
                    rec_path = urlparse(rec_url).path.rstrip("/")
                except Exception:
                    rec_path = ""
                if rec_path and rec_path == cur_path:
                    return fdata          # exact page match — return immediately
                # Keep as fallback but prefer a closer match
                if best is None:
                    best = fdata
            else:
                if best is None:
                    best = fdata

        return best

    def _find_field_url_from_events(self, fdata: Dict) -> str:
        """Return the URL where this field was recorded (fast path: page_url key)."""
        # New recorder stores page_url directly on the field entry
        if fdata.get("page_url"):
            return fdata["page_url"]
        # Fallback: scan raw_events for older pattern files that lack page_url
        if not self.pattern:
            return ""
        target_id   = fdata.get("meta", {}).get("id", "")
        target_name = fdata.get("meta", {}).get("name", "")
        for ev in self.pattern.get("raw_events", []):
            if ev.get("event_type") != "field_fill":
                continue
            m = ev.get("meta", {})
            if (target_id  and m.get("id")   == target_id) or \
               (target_name and m.get("name") == target_name):
                return ev.get("url", "")
        return ""

    def get_tab_order(self) -> List[str]:
        if not self.pattern:
            return []
        return self.pattern.get("session_summary", {}).get("tab_order", [])

    # ── Visual debugger ───────────────────────────────────────────────────────

    def _highlight(self, el: Any) -> None:
        if not self.visual_debug:
            return
        try:
            self.driver.execute_script(_JS_HIGHLIGHT, el)
            time.sleep(0.15)
        except Exception:
            pass

    def _unhighlight(self, el: Any) -> None:
        if not self.visual_debug:
            return
        try:
            self.driver.execute_script(_JS_UNHIGHLIGHT, el)
        except Exception:
            pass

    # ── Self-healing snapshot ─────────────────────────────────────────────────

    def _snapshot(self, label: str) -> None:
        """Capture a screenshot and full DOM dump for debugging."""
        os.makedirs(self.debug_dir, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:50]
        try:
            ss = os.path.join(self.debug_dir, f"{ts}_{safe}.png")
            self.driver.save_screenshot(ss)
            self.logger.warning(f"[UICtrl] Screenshot → {ss}")
        except Exception:
            pass
        try:
            dom = os.path.join(self.debug_dir, f"{ts}_{safe}_dom.html")
            with open(dom, "w", encoding="utf-8") as fh:
                fh.write(self.driver.page_source)
            self.logger.warning(f"[UICtrl] DOM dump   → {dom}")
        except Exception:
            pass

    # ── IFrame handling ───────────────────────────────────────────────────────

    def restore_main_frame(self) -> None:
        try:
            self.driver.switch_to.default_content()
            self._iframe_ctx = None
        except Exception:
            pass

    def _scan_iframes(self, find_fn) -> Optional[Any]:
        """
        Switch into every iframe on the page and call find_fn().
        Returns the first non-None result, leaving the driver inside that iframe.
        Restores main context if nothing found.
        """
        self.restore_main_frame()
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        self.logger.debug(f"[UICtrl] Scanning {len(iframes)} iframe(s)")
        for idx, iframe in enumerate(iframes):
            el = None
            try:
                self.driver.switch_to.frame(iframe)
                el = find_fn()
                if el:
                    self._iframe_ctx = idx
                    self.logger.debug(f"[UICtrl] Found element in iframe[{idx}]")
                    return el
            except (InvalidSwitchToTargetException, NoSuchFrameException):
                pass
            except Exception:
                pass
            if not el:
                try:
                    self.driver.switch_to.default_content()
                except Exception:
                    pass
        self.restore_main_frame()
        return None

    # ── Fuzzy Finder ──────────────────────────────────────────────────────────

    def fuzzy_find(
        self,
        hints:        List[str],
        el_type:      str            = "input",
        pattern_meta: Optional[Dict] = None,
        timeout:      Optional[float] = None,   # kept for API compat
    ) -> Optional[Any]:
        """
        Multi-strategy element finder.

        Strategy order (main document first, then iframes):
          1. Recorded pattern: id, name, css_selector, xpath
          2. Hint × attribute matrix (name, id, placeholder, autocomplete,
             aria-label, data-testid)
          3. XPath label-based lookup
          4. Generic type fallbacks
        """
        strategies = self._build_strategies(hints, el_type, pattern_meta)

        # Phase 1 — main document (instant, no timeout burn)
        el = self._try_strategies(strategies)
        if el:
            return el

        # Brief wait and retry once — handles slow-rendering SPAs
        time.sleep(1.5)
        el = self._try_strategies(strategies)
        if el:
            return el

        # Phase 2 — iframes
        self.logger.debug(f"[UICtrl] {hints} not in main frame — scanning iframes…")
        def _in_iframe():
            return self._try_strategies(strategies)
        el = self._scan_iframes(_in_iframe)
        if el:
            return el

        # Failure — snapshot
        self.logger.warning(f"[UICtrl] fuzzy_find FAILED  hints={hints}")
        self._snapshot(f"fuzzy_find_{'_'.join(hints[:2])}")
        return None

    def _build_strategies(
        self,
        hints:        List[str],
        el_type:      str,
        pattern_meta: Optional[Dict],
    ) -> List[Tuple[str, str, str]]:
        strategies: List[Tuple[str, str, str]] = []

        # ── 1. Recorded pattern metadata (highest priority)
        if pattern_meta:
            m = pattern_meta.get("meta", {})
            if m.get("id"):
                strategies.append(("pat:id",   By.ID,           m["id"]))
            if m.get("name"):
                strategies.append(("pat:name", By.NAME,         m["name"]))
            if m.get("css_selector"):
                strategies.append(("pat:css",  By.CSS_SELECTOR, m["css_selector"]))
            if m.get("xpath"):
                strategies.append(("pat:xpath", By.XPATH,       m["xpath"]))

        # ── 2. Hint × attribute matrix
        attrs = ["name", "id", "placeholder", "autocomplete",
                 "aria-label", "data-testid", "data-field"]
        for hint in hints:
            for attr in attrs:
                css = f"{el_type}[{attr}*='{hint}' i]:not([type='hidden'])"
                strategies.append((f"hint:{attr}={hint}", By.CSS_SELECTOR, css))

            # XPath label-based lookup
            xp = (
                f"//label[contains(translate(normalize-space(.),"
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'{hint}')]"
                f"/following::{el_type}[1]"
            )
            strategies.append((f"hint:label={hint}", By.XPATH, xp))

        # ── 3. Generic type fallbacks
        if el_type == "input":
            if any("pass" in h.lower() for h in hints):
                strategies.append(("fb:password", By.CSS_SELECTOR, "input[type='password']"))
            # email-type inputs are valid username fields on many systems
            is_user_field = any(h in ("username", "email", "user", "login", "id", "account")
                                for h in hints)
            if is_user_field:
                strategies.append(("fb:type=email", By.CSS_SELECTOR, "input[type='email']"))
            strategies.append(("fb:type=text", By.CSS_SELECTOR, "input[type='text']"))

        return strategies

    def _try_strategies(
        self,
        strategies: List[Tuple[str, str, str]],
        timeout:    float = 0,   # kept for API compat, no longer used
    ) -> Optional[Any]:
        """
        Iterate strategies using instant find_elements (no per-strategy wait).
        This eliminates the N×timeout hang when many strategies are tried.
        A single short implicit wait is set on the driver before calling,
        so the first strategy that matches a just-rendered element still works.
        """
        seen: set = set()
        for desc, by, selector in strategies:
            if (by, selector) in seen:
                continue
            seen.add((by, selector))
            try:
                els = self.driver.find_elements(by, selector)
                for el in els:
                    try:
                        if el.is_displayed():
                            self.logger.debug(f"[UICtrl] Found via {desc}: {selector!r}")
                            return el
                    except Exception:
                        continue
            except Exception as e:
                self.logger.debug(f"[UICtrl] Strategy {desc} error: {e}")
        return None

    # ── Human-mimicry fill ────────────────────────────────────────────────────

    def human_fill(
        self,
        el,
        value:         str,
        latency_ms:    float = 300,
        use_tab_after: bool  = True,
        is_password:   bool  = False,
        char_delay:    float = 0.04,
    ) -> bool:
        """
        Fill an element with human-like timing and stale-element recovery.

        Execution order:
          1. Scroll into view + honour recorded latency
          2. JS-clear (safe for React/Vue controlled inputs)
          3. Character-by-character send_keys
          4. Dispatch change event
          5. Tab if use_tab_after
        Falls back to direct JS value injection on ElementNotInteractableException.
        """
        for attempt in range(self.STALE_RETRIES):
            try:
                self._highlight(el)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center',inline:'nearest'});", el)
                # Honour recorded inter-field latency (cap at 1.5 s)
                time.sleep(min(latency_ms / 1000.0, 1.5))

                # JS-clear to reset React/Vue state
                self.driver.execute_script(
                    "arguments[0].value='';"
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));", el)
                el.clear()

                # Typed character-by-character
                for ch in value:
                    el.send_keys(ch)
                    time.sleep(char_delay)

                # Notify SPA frameworks
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", el)

                if use_tab_after:
                    el.send_keys(Keys.TAB)
                    time.sleep(0.1)

                self._unhighlight(el)
                masked = "***" if is_password else (value[:20] + ("…" if len(value) > 20 else ""))
                self.logger.debug(f"[UICtrl] Filled [{masked}]  latency={latency_ms:.0f}ms")
                return True

            except StaleElementReferenceException:
                self.logger.debug(
                    f"[UICtrl] StaleElement on fill  attempt {attempt+1}/{self.STALE_RETRIES}")
                if attempt < self.STALE_RETRIES - 1:
                    time.sleep(0.4)
                    continue
                self._snapshot("stale_fill")
                return False

            except ElementNotInteractableException:
                # JS injection fallback
                try:
                    self.driver.execute_script(_JS_FILL, el, value)
                    if use_tab_after:
                        el.send_keys(Keys.TAB)
                    self._unhighlight(el)
                    self.logger.debug("[UICtrl] JS-injection fill fallback used")
                    return True
                except Exception as js_err:
                    self.logger.warning(f"[UICtrl] JS fill fallback failed: {js_err}")
                    self._snapshot("not_interactable_fill")
                    return False

            except Exception as e:
                self.logger.warning(f"[UICtrl] human_fill error (attempt {attempt+1}): {e}")
                if attempt < self.STALE_RETRIES - 1:
                    time.sleep(0.3)
                    continue
                self._snapshot("fill_error")
                return False

        return False

    # ── Human-mimicry click ───────────────────────────────────────────────────

    def human_click(self, el, latency_ms: float = 200) -> bool:
        """Click with visual highlight, latency, and stale-element recovery."""
        for attempt in range(self.STALE_RETRIES):
            try:
                self._highlight(el)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(min(latency_ms / 1000.0, 1.0))
                el.click()
                self._unhighlight(el)
                return True

            except StaleElementReferenceException:
                self.logger.debug(
                    f"[UICtrl] StaleElement on click  attempt {attempt+1}/{self.STALE_RETRIES}")
                if attempt < self.STALE_RETRIES - 1:
                    time.sleep(0.4)
                    continue
                self._snapshot("stale_click")
                return False

            except ElementNotInteractableException:
                try:
                    self.driver.execute_script("arguments[0].click();", el)
                    self._unhighlight(el)
                    return True
                except Exception:
                    self._snapshot("not_interactable_click")
                    return False

            except Exception as e:
                self.logger.warning(f"[UICtrl] human_click error (attempt {attempt+1}): {e}")
                if attempt < self.STALE_RETRIES - 1:
                    time.sleep(0.3)
                    continue
                self._snapshot("click_error")
                return False

        return False

    # ── Submit button finder ──────────────────────────────────────────────────

    def find_submit(self, pattern_meta: Optional[Dict] = None) -> Optional[Any]:
        """
        Locate the form submit button using recorded pattern then generic selectors.
        Also scans iframes before returning None.
        """
        selectors: List[Tuple[str, str]] = []

        if pattern_meta:
            m = pattern_meta.get("meta", {})
            if m.get("id"):
                selectors.append((By.ID, m["id"]))
            if m.get("css_selector"):
                selectors.append((By.CSS_SELECTOR, m["css_selector"]))

        for css in [
            "input[type='submit']",
            "button[type='submit']",
            "button[aria-label*='login' i]",
            "button[aria-label*='sign in' i]",
            "button[aria-label*='log in' i]",
            "input[value*='login' i]",
            "input[value*='sign in' i]",
            "form button",
            "button",
        ]:
            selectors.append((By.CSS_SELECTOR, css))

        def _find():
            for by, sel in selectors:
                try:
                    elements = self.driver.find_elements(by, sel)
                    for el in elements:
                        try:
                            if not el.is_displayed():
                                continue
                            text = (el.text or "").strip().lower()
                            aria = (el.get_attribute("aria-label") or "").strip().lower()
                            value = (el.get_attribute("value") or "").strip().lower()
                            kind = " ".join(filter(None, [text, aria, value]))
                            if kind and any(k in kind for k in ["login", "log in", "sign in"]):
                                return el
                        except Exception:
                            continue
                except Exception:
                    pass
            for by, sel in selectors:
                try:
                    elements = self.driver.find_elements(by, sel)
                    for el in elements:
                        try:
                            if el.is_displayed():
                                return el
                        except Exception:
                            continue
                except Exception:
                    pass
            return None

        el = _find()
        if el:
            return el

        return self._scan_iframes(_find)

    def _expand_login_ui(self) -> None:
        """
        Expand common hidden login containers before locating fields.
        RMS keeps the admin login form inside a collapsed Bootstrap panel.
        """
        selectors = [
            (By.CSS_SELECTOR, "a[href='#collapseExample'][data-bs-toggle='collapse']"),
            (By.CSS_SELECTOR, "[data-bs-target='#collapseExample']"),
            (By.XPATH, "//a[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'log in here')]"),
            (By.XPATH, "//a[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'login here')]"),
            (By.XPATH, "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'log in')]"),
        ]

        try:
            panel = self.driver.find_elements(By.CSS_SELECTOR, "#collapseExample")
            if panel:
                classes = (panel[0].get_attribute("class") or "").lower()
                expanded = "show" in classes
                if expanded:
                    return
        except Exception:
            pass

        for by, sel in selectors:
            try:
                for el in self.driver.find_elements(by, sel):
                    try:
                        if not el.is_displayed():
                            continue
                        self.logger.debug(f"[UICtrl] Expanding login UI via {sel!r}")
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center',inline:'nearest'});", el
                        )
                        try:
                            el.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.8)
                        return
                    except Exception:
                        continue
            except Exception:
                continue

    # ── High-level login ──────────────────────────────────────────────────────

    def execute_login(
        self,
        username:  str,
        password:  str,
        login_url: Optional[str] = None,
    ) -> bool:
        """
        Full resilient login sequence:
          1. Navigate (if login_url provided)
          2. Fuzzy-find username + password fields
          3. Fill with human mimicry (latency from recorded pattern)
          4. Find and click submit (or Enter fallback)
          5. Detect success / failure
        """
        if login_url:
            try:
                self.driver.get(login_url)
                time.sleep(1.0)
            except Exception as e:
                self.logger.error(f"[UICtrl] Navigation failed: {e}")
                return False

        self._expand_login_ui()

        # Pull recorded patterns — scope to current page URL to avoid cross-page pollution
        cur_url  = self.driver.current_url
        user_pat = (self.get_field_pattern("username", cur_url) or
                    self.get_field_pattern("email",    cur_url))
        pass_pat = self.get_field_pattern("password", cur_url)

        # ── Locate username field
        user_el = self.fuzzy_find(
            hints        = ["username", "email", "user", "login", "id", "account"],
            el_type      = "input",
            pattern_meta = user_pat,
        )
        if not user_el:
            self.logger.error("[UICtrl] Username field not found")
            return False

        # ── Locate password field
        pass_el = self.fuzzy_find(
            hints        = ["password", "pass", "pwd", "secret"],
            el_type      = "input",
            pattern_meta = pass_pat,
        )
        if not pass_el:
            self.logger.error("[UICtrl] Password field not found")
            return False

        # ── Fill fields with recorded latency
        u_latency = (user_pat or {}).get("latency_ms", 300)
        p_latency = (pass_pat or {}).get("latency_ms", 300)

        ok_u = self.human_fill(user_el, username,
                               latency_ms=u_latency, use_tab_after=True,  is_password=False)
        ok_p = self.human_fill(pass_el, password,
                               latency_ms=p_latency, use_tab_after=False, is_password=True)

        if not ok_u or not ok_p:
            self.logger.warning("[UICtrl] One or more credential fields could not be filled")

        # ── Find submit button
        submit_pat = None
        if self.pattern:
            subs = self.pattern.get("session_summary", {}).get("submit_events", [])
            if subs:
                submit_pat = {"meta": subs[0].get("meta", {})}

        submit_el = self.find_submit(submit_pat)
        old_url   = self.driver.current_url

        if submit_el:
            self.human_click(submit_el, latency_ms=250)
        else:
            # Enter-key fallback
            self.logger.warning("[UICtrl] No submit button found — pressing Enter on password field")
            try:
                pass_el.send_keys(Keys.RETURN)
            except Exception:
                self.logger.error("[UICtrl] Enter fallback also failed")
                return False

        time.sleep(2.0)
        new_url = self.driver.current_url

        if new_url != old_url:
            self.logger.info(f"[UICtrl] Login succeeded  →  {new_url}")
            return True

        # Check for visible error messages
        src = self.driver.page_source.lower()
        if any(w in src for w in ["invalid", "incorrect", "failed", "error", "wrong", "denied"]):
            self.logger.warning("[UICtrl] Login failed — error message detected on page")
            self._snapshot("login_failed")
            return False

        # URL unchanged but no error = may be a SPA that stays on same URL
        self.logger.info("[UICtrl] URL unchanged, no error detected — treating as success")
        return True
