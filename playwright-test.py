"""
Check https://playwright.dev/python/docs/intro for more info.

$ pip install playwright
$ playwright install
$ python playwright-test.py

"""
import asyncio
import datetime
import os
import re
from itertools import count
from playwright.async_api import async_playwright, expect

BASE_URL = "http://127.0.0.1:8081/raydata"


def log_msg(msg):
    print(f"{datetime.datetime.now().isoformat()} {msg}")


async def main():
    async with async_playwright() as p:
        counter = count()
        log_msg("Launch a browser")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(timeout=60_000)  # in milliseconds

        log_msg(f"Go to {BASE_URL}")
        await page.goto(BASE_URL)

        await expect(page).to_have_title(re.compile("Raydata"))

        await expect(page.get_by_role("link", name="Examples", exact=True)).to_be_visible()

        log_msg("Taking a screenshot")
        await page.screenshot(path=f"screenshot-{next(counter):02d}.png", full_page=True)

        await page.get_by_role("link", name="Examples", exact=True).click()

        log_msg("Taking a screenshot")
        await page.screenshot(path=f"screenshot-{next(counter):02d}.png", full_page=True)

        await expect(page.get_by_role("link", name="CHX Analysis", exact=True)).to_be_visible()
        await page.get_by_role("link", name="CHX Analysis", exact=True).click()

        log_msg("Taking a screenshot")
        await page.screenshot(path=f"screenshot-{next(counter):02d}.png", full_page=True)

        log_msg("Close the browser")
        await browser.close()


if __name__ == "__main__":

    asyncio.run(main())

