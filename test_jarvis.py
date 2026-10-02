import asyncio
from playwright.async_api import async_playwright

async def run(query, output_file):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        print(f"Connecting to Jarvis UI admin panel...")
        await page.goto("http://172.17.89.72:8080/")
        
        await page.wait_for_selector("#u")
        await page.fill("#u", "jarvis")
        await page.fill("#p", "01102026")
        await page.click('button[type="submit"]')
        print("Logged in!")
        await asyncio.sleep(2)
        
        # Navigate to the chat tab in the admin panel
        # Looking at HTML, there are tabs. We can click the chat tab or just use the selector if it's visible.
        # Let's execute JS to show the chat tab
        await page.evaluate("document.querySelectorAll('.tab').forEach(t => t.style.display = 'none'); document.getElementById('tab-chat').style.display = 'block';")
        
        await page.fill("#chat-in", query)
        await page.click("#chat-form button")
        
        print(f"Asked: {query}")
        print("Waiting 15 seconds for LLM response...")
        await asyncio.sleep(15)
        
        await page.screenshot(path=f"Y:/05 Scambio/{output_file}")
        print(f"Screenshot saved to Y:/05 Scambio/{output_file}")
        
        # Extract text from chat
        chat_text = await page.inner_text("#chat")
        with open(f"Y:/05 Scambio/response.txt", "w", encoding="utf-8") as f:
            f.write(chat_text)
            
        await browser.close()

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "Fammi un documento di prova"
    out = sys.argv[2] if len(sys.argv) > 2 else "screenshot.png"
    asyncio.run(run(query, out))
