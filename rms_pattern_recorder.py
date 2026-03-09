#!/usr/bin/env python3
"""
RMS Behavioral Pattern Recorder v1.0

Records user interactions during a live manual session and exports ui_pattern.json.
The exported file is consumed by UIControlDriver to drive resilient, human-mimicry logins.

Usage:
    python rms_pattern_recorder.py --url http://localhost:8000
    python rms_pattern_recorder.py --url http://localhost:8000 --output login_pattern.json
    python rms_pattern_recorder.py --url http://localhost:8000 --browser firefox --poll 0.3
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.edge.service import Service as EdgeService
except ImportError:
    print("[!] Selenium not installed.  Run: pip install selenium webdriver-manager")
    sys.exit(1)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    HAS_WDM = True
except ImportError:
    HAS_WDM = False

# ─────────────────────────────────────────────────────────────────────────────
#  JavaScript injected into every visited page
# ─────────────────────────────────────────────────────────────────────────────

JS_RECORDER = r"""
(function () {
    if (window.__rmsRecorderActive) return;
    window.__rmsRecorderActive = true;
    window.__rmsEvents = window.__rmsEvents || [];
    var _lastTime = Date.now();

    /* ── Utility: Absolute XPath ── */
    function absoluteXPath(el) {
        if (!el || el.nodeType !== 1) return '';
        var parts = [];
        while (el && el.nodeType === Node.ELEMENT_NODE) {
            var idx = 1, sib = el.previousSibling;
            while (sib) {
                if (sib.nodeType === 1 && sib.tagName === el.tagName) idx++;
                sib = sib.previousSibling;
            }
            parts.unshift(el.tagName.toLowerCase() + '[' + idx + ']');
            el = el.parentNode;
        }
        return '/' + parts.join('/');
    }

    /* ── Utility: CSS Selector ── */
    function cssSelector(el) {
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return '#' + CSS.escape(el.id);
        var parts = [];
        var cur = el;
        while (cur && cur.nodeType === Node.ELEMENT_NODE && cur !== document.body) {
            var part = cur.tagName.toLowerCase();
            if (cur.id) { parts.unshift('#' + CSS.escape(cur.id)); break; }
            var classes = (typeof cur.className === 'string')
                ? cur.className.trim().split(/\s+/).filter(Boolean).slice(0, 2)
                : [];
            if (classes.length) part += '.' + classes.join('.');
            var n = 1, s = cur.previousSibling;
            while (s) { if (s.nodeType === 1 && s.tagName === cur.tagName) n++; s = s.previousSibling; }
            if (n > 1) part += ':nth-of-type(' + n + ')';
            parts.unshift(part);
            cur = cur.parentNode;
        }
        return parts.join(' > ');
    }

    /* ── Utility: Extract element metadata ── */
    function meta(el) {
        if (!el) return {};
        var labelText = '';
        if (el.id) {
            var lbl = document.querySelector('label[for="' + el.id + '"]');
            labelText = lbl ? lbl.innerText.trim() : '';
        }
        if (!labelText) {
            var p = el.closest('label');
            if (p) labelText = p.innerText.replace(el.value || '', '').trim();
        }
        var dataAttrs = {};
        Array.from(el.attributes || []).forEach(function (a) {
            if (a.name.startsWith('data-')) dataAttrs[a.name] = a.value;
        });
        return {
            tag:          (el.tagName || '').toLowerCase(),
            id:           el.id || '',
            name:         el.getAttribute('name') || '',
            class_name:   typeof el.className === 'string' ? el.className.trim() : '',
            type:         el.getAttribute('type') || '',
            placeholder:  el.getAttribute('placeholder') || '',
            aria_label:   el.getAttribute('aria-label') || '',
            label_text:   labelText,
            autocomplete: el.getAttribute('autocomplete') || '',
            role:         el.getAttribute('role') || '',
            data_attrs:   dataAttrs,
            css_selector: cssSelector(el),
            xpath:        absoluteXPath(el),
            visible:      !!(el.offsetWidth || el.offsetHeight || (el.getClientRects && el.getClientRects().length))
        };
    }

    /* ── Utility: Detect password field ── */
    function isPwd(el) {
        return el && (el.type === 'password' ||
            (el.getAttribute('autocomplete') || '').toLowerCase().includes('password'));
    }

    /* ── Utility: Infer data type ── */
    function dataType(el) {
        if (isPwd(el)) return 'password';
        var t = (el.type || '').toLowerCase();
        if (t === 'email') return 'email';
        if (t === 'number') return 'number';
        if (t === 'tel') return 'phone';
        if (t === 'date') return 'date';
        var n = (el.name || el.id || el.getAttribute('placeholder') || '').toLowerCase();
        if (/user|login|account/.test(n)) return 'username';
        if (/email/.test(n)) return 'email';
        if (/phone|tel|mobile/.test(n)) return 'phone';
        return 'text';
    }

    /* ── Core event recorder ── */
    function record(type, el, extra) {
        var now = Date.now();
        window.__rmsEvents.push(Object.assign({
            event_type: type,
            timestamp:  new Date(now).toISOString(),
            latency_ms: now - _lastTime,
            url:        window.location.href,
            meta:       meta(el)
        }, extra || {}));
        _lastTime = now;
    }

    /* ── Listener: Click ── */
    document.addEventListener('click', function (e) {
        var el = e.target;
        record('click', el, {
            text:      (el.innerText || el.value || '').trim().substring(0, 80),
            is_submit: (el.type === 'submit' || el.tagName === 'BUTTON'),
            coords:    { x: Math.round(e.clientX), y: Math.round(e.clientY) }
        });
    }, true);

    /* ── Listener: Special key presses ── */
    var SPECIAL = ['Tab','Enter','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight',
                   'Backspace','Delete','Home','End','PageUp','PageDown'];
    document.addEventListener('keydown', function (e) {
        if (SPECIAL.indexOf(e.key) === -1) return;
        record('keydown', e.target, {
            key:        e.key,
            is_special: true,
            shift:      e.shiftKey,
            ctrl:       e.ctrlKey,
            alt:        e.altKey
        });
    }, true);

    /* ── Listener: Field fill (on blur / change) ── */
    document.addEventListener('change', function (e) {
        var el = e.target;
        if (!['INPUT','TEXTAREA','SELECT'].includes(el.tagName)) return;
        var pwd = isPwd(el);
        record('field_fill', el, {
            value:        pwd ? '***MASKED***' : (el.value || '').substring(0, 200),
            value_length: (el.value || '').length,
            is_password:  pwd,
            data_type:    dataType(el)
        });
    }, true);

    /* ── Listener: Input snapshot (throttled, every 2 s) ── */
    document.addEventListener('input', function (e) {
        var el = e.target;
        if (!['INPUT','TEXTAREA'].includes(el.tagName)) return;
        var now = Date.now();
        if (!el.__rmsLast || (now - el.__rmsLast) > 2000) {
            el.__rmsLast = now;
            var pwd = isPwd(el);
            record('input_snapshot', el, {
                value_length: (el.value || '').length,
                is_password:  pwd,
                value_prefix: pwd ? '***' : (el.value || '').substring(0, 20)
            });
        }
    }, true);

    /* ── Listener: Focus / Blur for tab-order tracking ── */
    document.addEventListener('focus', function (e) {
        var el = e.target;
        if (!['INPUT','TEXTAREA','SELECT','BUTTON'].includes(el.tagName)) return;
        record('focus', el, {});
    }, true);

    document.addEventListener('blur', function (e) {
        var el = e.target;
        if (!['INPUT','TEXTAREA','SELECT','BUTTON'].includes(el.tagName)) return;
        record('blur', el, {});
    }, true);

    console.log('[RMS Recorder] Injected on ' + window.location.href);
})();
"""

JS_DRAIN         = "var e = window.__rmsEvents || []; window.__rmsEvents = []; return e;"
JS_ACTIVE_CHECK  = "return !!window.__rmsRecorderActive;"

# ─────────────────────────────────────────────────────────────────────────────
#  Driver factory
# ─────────────────────────────────────────────────────────────────────────────

def _create_driver(browser: str):
    if browser == "chrome":
        opts = ChromeOptions()
        for a in ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                  "--window-size=1280,900", "--ignore-certificate-errors"]:
            opts.add_argument(a)
        if HAS_WDM:
            return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)
        return webdriver.Chrome(options=opts)

    if browser == "firefox":
        opts = FirefoxOptions()
        opts.accept_insecure_certs = True
        if HAS_WDM:
            return webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=opts)
        return webdriver.Firefox(options=opts)

    if browser == "edge":
        opts = EdgeOptions()
        for a in ["--no-sandbox", "--ignore-certificate-errors"]:
            opts.add_argument(a)
        if HAS_WDM:
            return webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=opts)
        return webdriver.Edge(options=opts)

    raise ValueError(f"Unsupported browser: {browser}")

# ─────────────────────────────────────────────────────────────────────────────
#  Session post-processing
# ─────────────────────────────────────────────────────────────────────────────

def _build_session_summary(events: list) -> dict:
    fills   = [e for e in events if e["event_type"] == "field_fill"]
    submits = [e for e in events if e.get("is_submit")]

    # Build per-field map keyed by best available identifier
    # Use FIRST fill per field (preserves login-page entry over later same-name fields)
    fields: dict = {}
    for ev in fills:
        m = ev.get("meta", {})
        key = m.get("name") or m.get("id") or m.get("placeholder") or m.get("css_selector", "unknown")
        if key in fields:
            continue  # keep first occurrence (login page comes before inner pages)
        fields[key] = {
            "meta":         m,
            "page_url":     ev.get("url", ""),   # URL of the page where this field was filled
            "data_type":    ev.get("data_type", "text"),
            "is_password":  ev.get("is_password", False),
            "value_length": ev.get("value_length", 0),
            "value":        ev.get("value", ""),
            "latency_ms":   ev.get("latency_ms", 0),
        }

    # Infer tab order from focus/field_fill sequence
    seen: set = set()
    tab_order: list = []
    for ev in events:
        if ev["event_type"] in ("focus", "field_fill"):
            m = ev.get("meta", {})
            k = m.get("name") or m.get("id") or m.get("placeholder") or ""
            if k and k not in seen:
                seen.add(k)
                tab_order.append(k)

    return {
        "fields":        fields,
        "tab_order":     tab_order,
        "tab_count":     sum(1 for e in events
                             if e["event_type"] == "keydown" and e.get("key") == "Tab"),
        "submit_events": [{"text": s.get("text",""), "meta": s.get("meta",{})} for s in submits],
        "total_events":  len(events),
        "login_url":     events[0]["url"] if events else "",
    }

# ─────────────────────────────────────────────────────────────────────────────
#  Main recording loop
# ─────────────────────────────────────────────────────────────────────────────

def _driver_is_alive(driver) -> bool:
    try:
        if not getattr(driver, "session_id", None):
            return False
        driver.window_handles
        return True
    except (InvalidSessionIdException, WebDriverException):
        return False
    except Exception:
        return True

def record(url: str, output: str, browser: str, poll: float) -> None:
    print(f"[*] Launching {browser}  →  {url}")
    print("[*] Interact with the page normally.")
    print("[*] Close the browser window  OR  press Ctrl+C to stop recording.\n")

    driver = _create_driver(browser)
    driver.set_page_load_timeout(30)
    driver.get(url)
    driver.execute_script(JS_RECORDER)

    all_events: list = []
    last_url         = driver.current_url
    session_start    = datetime.now().isoformat()
    transient_failures = 0

    try:
        while True:
            time.sleep(poll)
            try:
                cur = driver.current_url
                transient_failures = 0
            except (InvalidSessionIdException, WebDriverException):
                transient_failures += 1
                if not _driver_is_alive(driver):
                    print("\n[*] Browser session closed.")
                    break
                if transient_failures >= 10:
                    print("\n[!] Recorder lost contact with the page repeatedly; preserving captured events.")
                    break
                continue
            except Exception:
                transient_failures += 1
                if transient_failures >= 10 and not _driver_is_alive(driver):
                    print("\n[*] Browser session closed.")
                    break
                continue

            # Re-inject on navigation
            if cur != last_url:
                last_url = cur
                time.sleep(0.5)
                try:
                    driver.execute_script(JS_RECORDER)
                    print(f"[~] Navigated → {cur}")
                except Exception:
                    pass

            # Re-inject if lost (SPA framework may have replaced the DOM)
            try:
                if not driver.execute_script(JS_ACTIVE_CHECK):
                    driver.execute_script(JS_RECORDER)
            except Exception:
                pass

            # Drain buffered events
            try:
                batch = driver.execute_script(JS_DRAIN) or []
            except Exception:
                batch = []

            if batch:
                all_events.extend(batch)
                print(f"[+] +{len(batch):>3} events  (total {len(all_events):>4})",
                      end="\r", flush=True)

    except KeyboardInterrupt:
        print("\n[*] Stopped by user.")
    except Exception as e:
        print(f"\n[!] Session ended: {e}")

    # Final drain
    try:
        batch = driver.execute_script(JS_DRAIN) or []
        all_events.extend(batch)
    except Exception:
        pass
    try:
        driver.quit()
    except Exception:
        pass

    if not all_events:
        print("[!] No events captured — was the page interacted with?")
        return

    summary = _build_session_summary(all_events)

    payload = {
        "meta": {
            "recorder_version": "1.0",
            "session_start":    session_start,
            "session_end":      datetime.now().isoformat(),
            "target_url":       url,
            "browser":          browser,
            "total_events":     len(all_events),
        },
        "session_summary": summary,
        "raw_events":      all_events,
    }

    out = os.path.abspath(output)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)

    print(f"\n[✓] Recorded {len(all_events)} events  →  {out}")
    print(f"    Fields    : {list(summary['fields'].keys())}")
    print(f"    Tab order : {summary['tab_order']}")
    print(f"    Submits   : {len(summary['submit_events'])}")

# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="RMS Behavioral Pattern Recorder — captures UI interactions and exports ui_pattern.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python rms_pattern_recorder.py --url http://localhost:8000
  python rms_pattern_recorder.py --url http://localhost:8000 --output login_pattern.json
  python rms_pattern_recorder.py --url http://localhost:8000 --browser firefox --poll 0.3
""")
    parser.add_argument("--url",     required=True,
                        help="Target URL to record interactions on")
    parser.add_argument("--output",  default="ui_pattern.json",
                        help="Output JSON file (default: ui_pattern.json)")
    parser.add_argument("--browser", default="chrome",
                        choices=["chrome", "firefox", "edge"],
                        help="Browser to use (default: chrome)")
    parser.add_argument("--poll",    type=float, default=0.5,
                        help="Event poll interval in seconds (default: 0.5)")
    args = parser.parse_args()
    record(args.url, args.output, args.browser, args.poll)


if __name__ == "__main__":
    main()
