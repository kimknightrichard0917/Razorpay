# ============================================================
# SINGLE FILE — RAZORPAY TELEGRAM BOT
# ============================================================
# BAS YE EK FILE COPY KARO AUR CHALAO!
# ============================================================

import logging
import requests
import re
import time
import random
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ─── CONFIG ──────────────────────────────────────────────────
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # <-- BAS YAHAN APNA TOKEN DAALO

DORKS = [
    'inurl:razorpay.me/@',
    'inurl:rzp.io/l/',
    'site:pages.razorpay.com',
    'inurl:razorpay.me/@ "donation"',
    'inurl:razorpay.me/@ "subscription"',
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Mozilla/5.0 (Android 12; Mobile; rv:68.0) Gecko/68.0 Firefox/68.0'
]

# ─── PROXY MANAGER ───────────────────────────────────────────
class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.load_proxies()
    
    def load_proxies(self):
        try:
            with open('proxies.txt', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.proxies.append(line)
        except:
            pass
    
    def get_proxy(self):
        if not self.proxies:
            return None
        proxy = random.choice(self.proxies)
        return {'http': proxy, 'https': proxy}
    
    def add_proxy(self, proxy):
        self.proxies.append(proxy)
        with open('proxies.txt', 'a') as f:
            f.write(proxy + '\n')
    
    def count(self):
        return len(self.proxies)

# ─── SCRAPER ─────────────────────────────────────────────────
class RazorpayScraper:
    def __init__(self):
        self.proxy_manager = ProxyManager()
    
    def search_dork(self, dork):
        results = []
        url = f"https://www.google.com/search?q={dork}&num=20"
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        proxy = self.proxy_manager.get_proxy()
        
        try:
            response = requests.get(url, headers=headers, proxies=proxy, timeout=30)
            if response.status_code == 200:
                for link in re.findall(r'https?://[^\s"]+', response.text):
                    if 'razorpay' in link or 'rzp.io' in link:
                        results.append(link)
        except:
            pass
        return results
    
    def scrape(self):
        all_links = []
        for dork in DORKS:
            links = self.search_dork(dork)
            all_links.extend(links)
            time.sleep(random.uniform(1, 2))
        return list(set(all_links))

# ─── TELEGRAM HANDLERS ──────────────────────────────────────
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("🔍 Search Dorks", callback_data="search")],
        [InlineKeyboardButton("📂 Add Proxy", callback_data="add_proxy")],
        [InlineKeyboardButton("📊 View Proxies", callback_data="view_proxies")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    await update.message.reply_text(
        "🔥 *Razorpay Dork Scraper Bot*\n\n"
        "Find Razorpay payment links using Google Dorks.\n\n"
        "/start — Show menu\n"
        "/search — Search all dorks\n"
        "/addproxy — Add proxy\n"
        "/viewproxy — View proxies",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def search_dorks(update: Update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔍 Searching... Please wait.")
    
    scraper = RazorpayScraper()
    results = scraper.scrape()
    
    if results:
        filename = f"razorpay_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w') as f:
            for link in results:
                f.write(link + '\n')
        
        response = f"✅ Found {len(results)} links!\n\n"
        for i, link in enumerate(results[:5], 1):
            response += f"{i}. {link}\n"
        if len(results) > 5:
            response += f"\n... and {len(results)-5} more."
        
        await query.edit_message_text(response, parse_mode="Markdown")
        
        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=filename
            )
        os.remove(filename)
    else:
        await query.edit_message_text("❌ No results found.")

async def add_proxy(update: Update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📡 Send proxy in format:\n"
        "`http://user:pass@ip:port`\n\n"
        "Example: `http://user123:pass456@192.168.1.1:8080`",
        parse_mode="Markdown"
    )

async def view_proxies(update: Update, context):
    query = update.callback_query
    await query.answer()
    pm = ProxyManager()
    if pm.count() > 0:
        await query.edit_message_text(f"📡 Active proxies: {pm.count()}")
    else:
        await query.edit_message_text("❌ No proxies added.")

async def help_command(update: Update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "❓ *Commands:*\n"
        "/start — Menu\n"
        "/search — Search dorks\n"
        "/addproxy — Add proxy\n"
        "/viewproxy — View proxies\n\n"
        "🔍 *Dorks:*\n"
        "• inurl:razorpay.me/@\n"
        "• inurl:rzp.io/l/\n"
        "• site:pages.razorpay.com",
        parse_mode="Markdown"
    )

# ─── MAIN ────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(search_dorks, pattern="search"))
    app.add_handler(CallbackQueryHandler(add_proxy, pattern="add_proxy"))
    app.add_handler(CallbackQueryHandler(view_proxies, pattern="view_proxies"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="help"))
    
    print("🔥 Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
