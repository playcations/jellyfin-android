"""Real Chromium keyboard/touch tests using the unmodified upstream command dispatcher.
Run: tests/.venv/bin/python tests/test_navigation.py [--web-source PATH] [--artifacts PATH]
No server, Jellyfin instance, credentials or network devices are used.
"""
import argparse
import os
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--web-source', type=Path, default=Path(__file__).resolve().parent / 'fixtures/jellyfin-web-12.2')
parser.add_argument('--artifacts', type=Path, default=Path('build/navigation-test-artifacts'))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
args.artifacts.mkdir(parents=True, exist_ok=True)
HTML = '''<!DOCTYPE html><html><head><style>
body { margin:0;background:#171a22;color:white;font:20px sans-serif; }
button,a,input,[role=button] { display:inline-block;box-sizing:border-box;width:140px;height:64px;margin:15px;padding:10px;background:#344050;color:white; }
.row { display:flex; width:650px; } .scroller { width:400px;overflow:auto; } .wide { display:flex;width:1000px; }
.dialog {position:fixed;inset:90px 100px;background:#233;z-index:10;} .hide {display:none!important;}
.spacer {height:700px;} input {width:240px;} [role=button] {cursor:pointer;}
</style></head><body>
<div id="home">
<div class="row modern"><button id="modern">Modern card</button><button id="modern2">Modern menu</button><div id="role" role="button" tabindex="0">Role button</div></div>
<div class="row itemsContainer"><div class="card" data-id="one"><a id="legacy" class="cardImageContainer itemAction" href="#item/one">Legacy card</a></div><div class="card" data-id="two"><a id="legacy2" class="cardImageContainer itemAction" href="#item/two">Legacy two</a></div><button id="disabled" disabled>Disabled</button></div>
<div class="row"><input id="text" value="hello world"><button id="typing-next">Next</button></div>
<div class="scroller" id="scroller"><div class="wide"><button id="s1">S1</button><button id="s2">S2</button><button id="s3">S3</button><button id="s4">S4</button><button id="s5">S5</button></div></div>
<div class="spacer"></div><button id="bottom">Bottom</button>
<button id="hidden" hidden>Hidden</button><button id="aria-hidden" aria-hidden="true">ARIA hidden</button>
</div></body></html>'''

def module(path, tail):
    source = path.read_text()
    source = re.sub(r'^import .*?;\n', '', source, flags=re.M)
    source = re.sub(r'export default \{', 'const defaultExport = {', source)
    source = re.sub(r'export (class|function) ', r'\1 ', source)
    return '(() => {\n' + source + '\n' + tail + '\n})();'

setup = '''window.calls=[];window.activations=[];window.routeBack=0;
window.dom={addEventListener:(s,e,f,o)=>s.addEventListener(e,f,o),removeEventListener:(s,e,f,o)=>s.removeEventListener(e,f,o),parentWithClass:(s,c)=>s.closest('.'+c)};
window.scrollManager={isEnabled:()=>false};window.appHost={supports:()=>true,exit:()=>window.exits=(window.exits||0)+1};
window.AppFeature={Exit:'exit'};window.playbackManager={};window.appRouter={canGoBack:()=>true,back:()=>window.routeBack++};
document.addEventListener('click',e=>{if(e.target.closest('button,a,[role=button]')) {window.activations.push(e.target.closest('button,a,[role=button]').id); if(e.target.id!=='submit') e.preventDefault();}});
'''
focus = module(args.web_source / 'src/components/focusManager.js', 'window.focusManager=defaultExport;')
manager = module(args.web_source / 'src/scripts/inputManager.js', '''window.inputManager=defaultExport;
const original=window.inputManager.handleCommand;window.inputManager.handleCommand=(c,o)=>{calls.push(c);original(c,o);};''')
adapter = module(root / 'app/src/main/assets/native/PhysicalInputAdapter.js', 'window.PhysicalInputAdapter=PhysicalInputAdapter;')
plugin = module(root / 'app/src/main/assets/native/NavigationPlugin.js', 'window.NavigationPlugin=NavigationPlugin;')
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'))
    context = browser.new_context(viewport={'width': 900, 'height': 600}, has_touch=True)
    page = context.new_page()
    def route_fixture(route):
        if '/native/' in route.request.url:
            filename = route.request.url.split('/native/', 1)[1].split('?', 1)[0]
            route.fulfill(body=(root/'app/src/main/assets/native'/filename).read_text(), content_type='text/javascript')
        else:
            route.fulfill(body=HTML, content_type='text/html')
    page.route('http://fixture.test/**', route_fixture)
    def reset(enabled=True):
        page.goto('http://fixture.test/', wait_until='networkidle')
        page.evaluate(setup)
        page.evaluate(focus)
        page.evaluate(manager)
        page.evaluate(adapter)
        page.evaluate(plugin)
        page.evaluate('''enabled=>{window.NativeShell={capabilities:{physicalNavigation:enabled}};
            window.plugin=new NavigationPlugin({inputManager,playbackManager});
            // A second web keyboard listener would duplicate unclaimed keys.
            window.addEventListener('keydown',e=>{if(!e.defaultPrevented&&e.key==='ArrowRight')window.webKeyCalls=(window.webKeyCalls||0)+1;});
        }''', enabled)
        if enabled: expect(page.locator('#modern')).to_be_focused()
    def active(id): expect(page.locator('#'+id)).to_be_focused()
    def check(name, fn):
        reset()
        fn()
        results.append({'name': name, 'status': 'passed'})
        print('PASS', name, flush=True)
    def directional():
        page.keyboard.press('ArrowRight'); active('modern2')
        page.keyboard.press('ArrowDown'); active('legacy2')
        page.keyboard.press('ArrowLeft'); active('legacy')
        page.keyboard.press('Enter')
        assert page.evaluate('activations') == ['legacy']
        assert page.evaluate('calls') == ['right','down','left']
        assert page.evaluate('window.webKeyCalls||0') == 0
        assert page.evaluate("getComputedStyle(document.activeElement).outlineWidth") == '3px'
    check('Modern and legacy cards, activation, single dispatch and visible ring', directional)
    def typing():
        page.locator('#text').focus()
        page.keyboard.press('End'); page.keyboard.press('ArrowLeft'); page.keyboard.type('!')
        expect(page.locator('#text')).to_have_value('hello worl!d'); active('text')
        for key in ['ArrowUp','ArrowDown','Shift+ArrowLeft','Control+ArrowRight','Alt+ArrowRight','Meta+ArrowRight','Enter']:
            page.keyboard.press(key)
        active('text'); assert not any(c in ['left','right','up','down','select'] for c in page.evaluate('calls'))
        page.evaluate("document.querySelector('#text').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft',isComposing:true,bubbles:true,cancelable:true}))")
        assert not page.evaluate('calls')
        page.keyboard.press('Tab'); active('typing-next')
        page.keyboard.press('Enter'); assert page.evaluate('activations.at(-1)') == 'typing-next'
    check('Caret, typing, composition, modifiers, native Enter and Tab', typing)
    def controls():
        page.evaluate("document.querySelector('#text').outerHTML='<div contenteditable=true id=text>editable</div><select id=select><option>A</option><option>B</option></select><input type=range id=range><textarea id=textarea>words</textarea>'")
        for id in ['text','select','range','textarea']:
            page.locator('#'+id).focus(); page.keyboard.press('ArrowRight'); page.keyboard.press('ArrowDown'); active(id)
        assert not any(c in ['right','down'] for c in page.evaluate('calls'))
    check('Contenteditable, select, range and textarea retain editing', controls)
    def checkbox():
        page.evaluate("document.querySelector('#modern').outerHTML='<input type=checkbox id=checkbox>'")
        page.locator('#checkbox').focus();page.keyboard.press('Space')
        assert page.locator('#checkbox').is_checked()
        page.keyboard.press('ArrowRight');active('modern2')
    check('Checkbox retains native toggle and permits directional exit', checkbox)
    def checkable_enter():
        page.evaluate('''document.querySelector('#modern').outerHTML='<input type="checkbox" id="check-enter"><input type="radio" name="fixture-radio" id="radio-one" checked><input type="radio" name="fixture-radio" id="radio-two">';''')
        page.locator('#check-enter').focus(); page.keyboard.press('Enter')
        assert page.locator('#check-enter').is_checked()
        page.keyboard.press('Space'); assert not page.locator('#check-enter').is_checked()
        page.locator('#radio-two').focus(); page.keyboard.press('Enter')
        assert page.locator('#radio-two').is_checked()
        assert not page.locator('#radio-one').is_checked()
    check('Remote Enter toggles native checkboxes and radios while Space remains native', checkable_enter)
    def transparent_checkable():
        page.evaluate('''() => {
            document.querySelector('#modern2').outerHTML='<span class="MuiCheckbox-root" style="position:relative;display:inline-block;width:140px;height:64px;margin:15px;background:#345"><input type="checkbox" id="mui-check" style="position:absolute;opacity:0;inset:0;width:100%;height:100%;margin:0"><span aria-hidden="true">Visible check artwork</span></span>';
        }''')
        page.locator('#modern').focus(); page.keyboard.press('ArrowRight'); active('mui-check')
        assert page.locator('.MuiCheckbox-root').evaluate("e=>getComputedStyle(e).outlineWidth") == '3px'
        page.evaluate("document.body.insertAdjacentHTML('beforeend','<span hidden>Mutation</span>')")
        page.wait_for_timeout(100); active('mui-check')
        page.keyboard.press('Enter'); assert page.locator('#mui-check').is_checked()
        page.locator('.MuiCheckbox-root').evaluate("e=>e.style.opacity='0'")
        page.keyboard.press('ArrowRight'); active('role')
    check('Transparent MUI inputs remain reachable, visibly focused and stable after mutations', transparent_checkable)
    def permanent_drawer():
        page.evaluate('''() => {
            document.querySelector('#home').style.marginLeft='250px';
            const drawer=document.createElement('aside'); drawer.className='MuiDrawer-root MuiDrawer-docked';
            drawer.style='position:fixed;left:0;top:0;width:230px;height:100%';
            drawer.innerHTML='<div class="MuiPaper-root"><button id="sidebar">Sidebar</button></div>';
            document.body.prepend(drawer);
        }''')
        page.locator('#sidebar').focus(); page.keyboard.press('ArrowRight'); active('modern')
        page.evaluate("document.body.insertAdjacentHTML('beforeend','<span hidden>Mutation</span>')")
        page.wait_for_timeout(100); active('modern')
        page.keyboard.press('ArrowLeft'); active('sidebar')
    check('Permanent widescreen drawers permit movement between sidebar and main content', permanent_drawer)
    def repeat():
        page.keyboard.down('ArrowRight'); active('modern2')
        page.keyboard.down('ArrowRight'); active('role'); page.keyboard.up('ArrowRight')
        page.keyboard.down('Enter'); page.keyboard.down('Enter'); page.keyboard.up('Enter')
        assert page.evaluate("activations.filter(x=>x==='role').length") == 1
        assert page.evaluate("calls.filter(x=>x==='right').length") == 2
        page.keyboard.down('Escape'); page.keyboard.down('Escape'); page.keyboard.up('Escape')
        assert page.evaluate('routeBack') == 1
    check('Arrow repeats navigate; select and Back repeats do not double activate', repeat)
    def dialog():
        page.locator('#legacy2').focus()
        page.evaluate('''() => {const d=document.createElement('div');d.className='dialog opened';d.id='dialog';d.innerHTML='<button id="menu1">Audio</button><button id="menu2">Subtitles</button>';document.body.append(d);
            inputManager.on(d,e=>{if(e.detail.command==='back'){e.preventDefault();d.remove();}});}''')
        active('menu1'); page.keyboard.press('ArrowRight'); active('menu2')
        page.keyboard.press('ArrowDown'); active('menu2')
        page.evaluate('plugin.goBack()'); active('legacy2')
        assert page.evaluate('routeBack') == 0
        page.evaluate('plugin.goBack()'); assert page.evaluate('routeBack') == 1
    check('Dialog scope, native Back interception and opener restoration', dialog)
    def route():
        page.locator('#legacy2').focus()
        page.evaluate("location.hash='detail'; document.querySelector('#home').classList.add('hide'); document.body.insertAdjacentHTML('beforeend','<div id=detail><button id=play>Play</button></div>')")
        active('play')
        page.evaluate("location.hash='';document.querySelector('#detail').remove();document.querySelector('#home').classList.remove('hide')")
        active('legacy2')
        page.evaluate("const e=document.querySelector('#legacy2');e.replaceWith(e.cloneNode(true))")
        active('legacy2')
        page.evaluate('window.dispatchEvent(new Event("focus"))'); active('legacy2')
    check('Route, recreated legacy cards and playback window focus restoration', route)
    def scroll():
        page.locator('#s1').focus()
        for _ in range(4): page.keyboard.press('ArrowRight')
        active('s5'); assert page.locator('#scroller').evaluate('(e)=>e.scrollLeft') > 200
        page.locator('#bottom').focus()
        assert page.evaluate('window.scrollY') > 400
        box=page.locator('#bottom').bounding_box(); assert box['y']+box['height'] <= 600
    check('Horizontal overflow and vertical focus scroll into view', scroll)
    def cancelled():
        page.locator('#modern').focus()
        page.evaluate("inputManager.on(document.querySelector('#modern'),e=>{if(e.detail.command==='right')e.preventDefault()})")
        page.keyboard.press('ArrowRight'); active('modern')
        page.evaluate("document.querySelector('#modern2').setAttribute('aria-disabled','true')")
        page.keyboard.press('ArrowDown'); active('legacy')
        page.keyboard.press('ArrowRight'); active('legacy2')
    check('Web controls consume commands before adapter and disabled targets excluded', cancelled)
    def invisible():
        page.evaluate("""document.querySelector('#modern2').style.opacity='0';document.querySelector('#role').setAttribute('aria-hidden','true');document.body.insertAdjacentHTML('beforeend','<div class=mainDrawer><button id=closed-nav>Closed nav</button></div><div style="opacity:0"><button id=transparent>Invisible overlay</button></div>')""")
        page.keyboard.press('ArrowRight')
        assert page.evaluate("!['modern2','role','closed-nav','transparent'].includes(document.activeElement.id)")
        assert page.evaluate("plugin.inputAdapter.elements(document.body).every(e=>!['modern2','role','closed-nav','transparent'].includes(e.id))")
    check('Transparent card overlays, hidden targets and closed drawer excluded', invisible)
    def modern_modal():
        page.locator('#modern2').focus()
        page.evaluate("""() => {const m=document.createElement('div'); m.className='MuiModal-root dialog';m.innerHTML='<div role=menu><button id=mui1>Settings</button><button id=mui2>More</button></div>';document.body.append(m); m.addEventListener('keydown',e=>{if(e.key==='Escape') {e.stopPropagation();m.remove();}});}""")
        active('mui1');page.keyboard.press('ArrowRight');active('mui2')
        page.evaluate('plugin.goBack()');active('modern2')
        assert page.evaluate('routeBack') == 0
    check('Modern MUI menu dismisses through its own Escape lifecycle', modern_modal)
    def modern_roving_menu():
        page.locator('#modern2').focus()
        page.evaluate('''() => {
            const modal=document.createElement('div'); modal.className='MuiModal-root dialog';
            modal.innerHTML='<div role="menu" style="display:flex;flex-direction:column"><button role="menuitem" id="roving1" tabindex="0">First</button><button role="menuitem" id="roving2" tabindex="-1">Second</button><button role="menuitem" id="roving3" tabindex="-1">Third</button></div>';
            modal.addEventListener('keydown',e=>{
                if(e.key!=='ArrowDown') return;
                e.preventDefault();
                const items=[...modal.querySelectorAll('[role="menuitem"]')];
                const index=items.indexOf(document.activeElement);
                items.forEach(item=>item.tabIndex=-1);
                const next=items[(index+1)%items.length]; next.tabIndex=0; next.focus();
            });
            document.body.append(modal);
        }''')
        active('roving1')
        page.keyboard.press('ArrowDown'); active('roving2')
        page.keyboard.press('ArrowDown'); active('roving3')
        assert not page.evaluate("calls.includes('down')")
    check('Modern roving-tabindex menus receive and consume their own arrow events', modern_roving_menu)
    def drawer():
        page.locator('#modern2').focus()
        page.evaluate("""() => {const d=document.createElement('div');d.className='mainDrawer drawer-open dialog';d.innerHTML='<button id=nav1>Home</button><button id=nav2>Live TV</button>';document.body.append(d);document.querySelector('#modern2').classList.add('mainDrawerButton'); document.querySelector('#modern2').onclick=()=>d.remove();}""")
        active('nav1'); page.keyboard.press('ArrowRight');active('nav2')
        page.evaluate('plugin.goBack()');active('modern2');assert page.evaluate('routeBack') == 0
    check('Legacy navigation drawer contains focus and Back closes via toggle', drawer)
    def form():
        page.evaluate("""() => {const f=document.createElement('form');f.innerHTML='<input id=formtext><button type=submit id=submit>Sign in</button>';f.onsubmit=e=>{e.preventDefault();window.submits=(window.submits||0)+1;};document.body.append(f);}""")
        page.locator('#formtext').focus(); page.keyboard.press('Enter')
        assert page.evaluate('window.submits') == 1
        page.locator('#submit').focus(); page.keyboard.press('Enter')
        # The fixture's click log cancels clicks, so native submit above is the assertion.
        assert page.evaluate('activations.at(-1)') == 'submit'
    check('Native Enter form submission and submit button semantics', form)
    def touch():
        page.locator('#modern2').tap()
        assert page.evaluate('activations') == ['modern2']
        assert not page.evaluate("document.documentElement.classList.contains('familyfin-physical-input')")
        page.evaluate("document.querySelector('#modern2').remove()")
        assert page.evaluate("!document.documentElement.classList.contains('familyfin-physical-input')")
        page.keyboard.press('ArrowDown')
        assert page.evaluate("document.documentElement.classList.contains('familyfin-physical-input')")
    check('Touch activation, no forced touch autofocus, remote resumes', touch)
    reset(False)
    assert page.evaluate('!plugin.inputAdapter')
    page.locator('#legacy').tap(); assert page.evaluate('activations') == ['legacy']
    page.locator('#text').fill('phone text'); page.keyboard.press('ArrowLeft')
    assert not any(c in ['left','right','up','down'] for c in page.evaluate('calls'))
    results.append({'name': 'Phone build capability leaves touch and keyboard unchanged', 'status': 'passed'})
    reset()
    page.evaluate("""window.NativeInterface={getDeviceInformation:()=>JSON.stringify({deviceId:'fixture',deviceName:'Fixture',appName:'Familyfin Web',appVersion:'test',physicalNavigation:true}),getCodecCapabilities:()=> '{}'}""")
    page.evaluate('(function(){'+(root/'app/src/main/assets/native/nativeshell.js').read_text()+'})()')
    assert page.evaluate('NativeShell.AppHost.getDefaultLayout()') == 'mobile'
    page.evaluate("""async () => {const Plugin = await window.NavigationPlugin(); window.plugin=new Plugin({inputManager,playbackManager});}""")
    page.keyboard.press('ArrowRight'); active('modern2')
    assert page.evaluate("calls.filter(x=>x==='right').length") == 1
    results.append({'name': 'Actual NativeShell plugin loader imports APK adapter, keeps mobile layout and replaces listeners once', 'status': 'passed'})
    reset()
    page.evaluate('plugin.inputAdapter.destroy()')
    page.keyboard.press('ArrowRight')
    assert page.evaluate('window.webKeyCalls') == 1
    assert not page.locator('style').filter(has_text='familyfin-physical-input').count()
    results.append({'name': 'Adapter teardown removes listeners and styling', 'status': 'passed'})
    page.screenshot(path=str(args.artifacts/'navigation-fixture.png'))
    browser.close()
(args.artifacts/'navigation-tests.json').write_text(json.dumps({'tests': results,'passed':len(results),'webSource':str(args.web_source)},indent=2)+'\n')
print(f'{len(results)} browser scenarios passed')
