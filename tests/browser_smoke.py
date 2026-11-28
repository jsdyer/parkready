"""Exercise the real built BC Parks catalogue at its project subpath."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import tempfile
import threading
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    screenshots=ROOT/'browser-checks';screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        shutil.copytree(ROOT/'dist',Path(temporary)/'parkready')
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=temporary))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH'))
                context=browser.new_context(viewport={'width':1280,'height':1000},accept_downloads=True)
                page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/parkready/')
                page.locator('.park-card').first.wait_for()
                assert 'protected areas' in page.locator('#stats').inner_text()
                page.locator('#search').fill('Golden Ears')
                assert page.locator('.park-card').count()==1
                page.locator('.park-card').click()
                assert 'Golden Ears' in page.locator('#details h2').inner_text()
                page.get_by_role('button',name='☆ Save park',exact=True).click()
                page.locator('#saved').check()
                assert page.locator('.park-card').count()==1
                page.locator('#date').fill('2027-07-01');page.locator('#date').dispatch_event('change')
                assert '2027-07-01' in page.locator('#details').inner_text()
                assert 'saved=' not in page.url
                page.evaluate("Object.defineProperty(navigator, 'clipboard', {value: {writeText: async () => {}}})")
                page.get_by_role('button',name='Copy plan link',exact=True).click()
                page.get_by_role('button',name='Link copied',exact=True).wait_for()
                with page.expect_download() as captured:page.get_by_role('button',name='Download plan',exact=True).click()
                assert captured.value.suggested_filename=='parkready-8-2027-07-01.txt'
                with page.expect_download() as captured:page.locator('#export').click()
                assert captured.value.suggested_filename=='parkready-results.csv'
                page.reload();page.locator('#details h2').wait_for()
                assert page.locator('#date').input_value()=='2027-07-01'
                assert 'Golden Ears' in page.locator('#details h2').inner_text()
                assert page.get_by_role('button',name='★ Remove saved',exact=True).count()==1
                page.screenshot(path=str(screenshots/'desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.screenshot(path=str(screenshots/'mobile.png'),full_page=True)
                page.locator('#search').fill('<img src=x onerror="alert(1)">')
                assert page.locator('#list img').count()==0
                assert 'No matching parks' in page.locator('#list').inner_text()
                page.locator('#reset').click();page.locator('#clear-saved').click();page.locator('#saved').check()
                assert 'No matching parks' in page.locator('#list').inner_text()
                page.locator('#reset').click();page.locator('#search').fill('Mount Robson');assert page.locator('.park-card').count()>0
                guide_browser = browser.new_context(java_script_enabled=False, viewport={'width':320,'height':640})
                static = guide_browser.new_page()
                static.goto(f'http://127.0.0.1:{server.server_port}/parkready/')
                static.get_by_role('link', name='Browse BC park visit guides by region').click()
                static.get_by_role('link',name='Lower Mainland and Fraser Valley',exact=True).click()
                static.get_by_role('link',name='Golden Ears Park',exact=True).click()
                assert static.locator('h1').inner_text() == 'Golden Ears Park visit guide'
                assert static.get_by_role('link',name='Check the official park page').get_attribute('href') == 'https://bcparks.ca/golden-ears-park/'
                assert static.evaluate('document.documentElement.scrollWidth <= innerWidth')
                guide_browser.close()
                # A transport failure must not create an empty-but-apparently-healthy catalogue.
                failed=context.new_page();failed.route('**/data/index.json',lambda route:route.fulfill(status=503,body='Unavailable'))
                failed.goto(f'http://127.0.0.1:{server.server_port}/parkready/')
                failed.locator('#freshness.stale').wait_for()
                assert 'Catalogue unavailable' in failed.locator('#stats').inner_text()
                assert not errors,errors
                browser.close()
            print('Browser checks passed: real catalogue, project path, filters, dates, favourites, clipboard, downloads, sharing, XSS, mobile and failed fetch')
        finally:server.shutdown()
if __name__=='__main__':main()
