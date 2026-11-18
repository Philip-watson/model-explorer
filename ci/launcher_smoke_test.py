# Copyright 2026 The AI Edge Model Explorer Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""Launcher regressions against a running server, using unittest + Playwright.

MODEL_EXPLORER_TEST_URL selects the UI (defaults to http://127.0.0.1:8080).
MODEL_EXPLORER_BROWSER_CHANNEL=msedge runs installed Edge.
MODEL_EXPLORER_PTE_MODEL optionally exercises a local PTE file and adapter.
"""

import json
import os
from pathlib import Path
import re
import unittest

from playwright.sync_api import sync_playwright, expect

try:
  from model_explorer import auth
except ImportError:
  auth = None

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / 'test/test_models'
URL = os.environ.get('MODEL_EXPLORER_TEST_URL', 'http://127.0.0.1:8080')


class LauncherSmokeTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.playwright = sync_playwright().start()
    cls.browser = cls.playwright.chromium.launch(
        channel=os.environ.get('MODEL_EXPLORER_BROWSER_CHANNEL'),
    )
    cls.token = auth.read_token_file(8080) if auth else None

  @classmethod
  def tearDownClass(cls):
    cls.browser.close()
    cls.playwright.stop()

  def setUp(self):
    self.context = self.browser.new_context(
        viewport={'width': 1440, 'height': 1024}, color_scheme='light'
    )
    if self.token:
      self.context.add_init_script(
          'sessionStorage.setItem("model_explorer_api_token", '
          + json.dumps(self.token)
          + ');'
      )
    self.page = self.context.new_page()
    self.page.goto(URL)
    expect(self.page.get_by_role('heading', name='Open models')).to_be_visible()

  def tearDown(self):
    self.context.close()

  def add_path(self, path):
    self.page.get_by_role('combobox', name='Path on this server').fill(
        str(path)
    )
    self.page.get_by_role('button', name='Add', exact=True).click()
    expect(
        self.page.get_by_role('combobox', name='Path on this server')
    ).to_have_value('')

  def open_models(self):
    self.page.get_by_role('button', name=re.compile(r'^Open models?$')).click()

  def test_painted_doors_and_real_environment(self):
    expect(
        self.page.get_by_role('button', name='Add', exact=True)
    ).to_be_disabled()
    for button, title in [
        ('Manage extensions', 'Manage extensions'),
        ('View diagnostics', 'Server diagnostics'),
    ]:
      self.page.get_by_role('button', name=button, exact=True).click()
      dialog = self.page.get_by_role('dialog')
      expect(dialog.get_by_role('heading', name=title)).to_be_visible()
      expect(dialog).to_contain_text('not available in this prototype yet')
      self.page.keyboard.press('Escape')
      expect(dialog).not_to_be_visible()
      expect(
          self.page.get_by_role('button', name=button, exact=True)
      ).to_be_focused()
    self.page.get_by_text('View all formats', exact=True).click()
    expect(self.page.locator('#formats-heading').locator('..')).to_contain_text(
        '.json'
    )
    self.page.get_by_text('View loaded extensions', exact=True).click()
    expect(self.page.get_by_text('JSON adapter', exact=True)).to_be_visible()

  def test_expanded_panels_reach_bottom_after_resize(self):
    self.add_path(MODELS / 'test_graph_original.json')
    self.add_path(MODELS / 'fully_connected.tflite')
    summaries = self.page.locator('.model-details summary')
    summaries.nth(0).click()
    summaries.nth(1).click()
    content = self.page.locator('home-page > .container > .content')
    extensions = self.page.get_by_text('View loaded extensions', exact=True)

    def assert_reachable(control):
      content.evaluate('element => element.scrollTop = element.scrollHeight')
      bounds = content.bounding_box()
      target = control.bounding_box()
      footer = self.page.locator('.utos').bounding_box()
      self.assertGreaterEqual(target['y'], bounds['y'])
      self.assertLessEqual(
          target['y'] + target['height'], bounds['y'] + bounds['height']
      )
      self.assertLessEqual(bounds['y'] + bounds['height'], footer['y'])
      self.assertLessEqual(
          footer['y'] + footer['height'], self.page.viewport_size['height']
      )

    for width, height in [(1280, 720), (1920, 1080), (1440, 600), (390, 680)]:
      with self.subTest(width=width, height=height):
        self.page.set_viewport_size({'width': width, 'height': height})
        frame = self.page.locator('home-page > .container').bounding_box()
        self.assertEqual(
            frame, {'x': 0, 'y': 0, 'width': width, 'height': height}
        )
        for selector in ['.title', '.utos']:
          self.assertEqual(
              self.page.locator('home-page ' + selector).bounding_box()[
                  'width'
              ],
              width,
          )
        self.assertAlmostEqual(
            self.page.locator('.model-source-input-container').bounding_box()[
                'width'
            ],
            content.evaluate("""element => {
              const style = getComputedStyle(element);
              return element.clientWidth - parseFloat(style.paddingLeft)
                  - parseFloat(style.paddingRight);
            }"""),
            delta=1,
        )
        if width > 900:
          assert_reachable(
              self.page.get_by_role('button', name='Copy details').last
          )
        extensions.click()
        assert_reachable(
            self.page.get_by_role('button', name='View diagnostics')
        )
        extensions.click()

  def test_every_setting_persists_and_themes_work(self):
    self.page.get_by_role('button', name='Settings', exact=True).click()
    dialog = self.page.get_by_role('dialog')
    items = dialog.locator('.setting-item')
    expect(items).to_have_count(20)
    changed = []
    for item in items.all():
      toggle = item.get_by_role('switch')
      if toggle.count():
        checked = not toggle.is_checked()
        toggle.click()
        expect(toggle).to_have_attribute('aria-checked', str(checked).lower())
        changed.append(('switch', toggle.get_attribute('aria-label'), checked))
        continue
      number = item.locator('input[type=number]')
      if number.count():
        value = format(float(number.input_value()) + 1, 'g')
        number.fill(value)
        number.blur()
        changed.append(('field', number.get_attribute('aria-label'), value))
        continue
      text = item.locator('textarea, input[type=text]')
      if text.count():
        value = (
            '#123456'
            if item.locator('input[type=color]').count()
            else 'Const,TestHiddenOp'
        )
        text.fill(value)
        text.blur()
        changed.append(('field', text.get_attribute('aria-label'), value))
    self.assertGreaterEqual(len(changed), 20)
    self.page.get_by_label('Appearance').select_option('dark')
    expect(self.page.locator('body')).to_have_attribute('data-metheme', 'dark')
    dialog.get_by_role('button', name='Close', exact=True).click()
    saved = self.page.evaluate(
        'localStorage.getItem("model_explorer_settings")'
    )
    self.assertEqual(len(json.loads(saved)), len(changed))
    self.page.reload()
    self.page.get_by_role('button', name='Settings', exact=True).click()
    for kind, label, value in changed:
      control = (
          self.page.get_by_role('switch', name=label, exact=True)
          if kind == 'switch'
          else self.page.get_by_label(label, exact=True)
      )
      if kind == 'switch':
        self.assertEqual(control.is_checked(), value, label)
      else:
        expect(control).to_have_value(value)
    expect(self.page.get_by_label('Appearance')).to_have_value('dark')
    self.page.get_by_label('Appearance').select_option('system')
    expect(self.page.locator('body')).to_have_attribute('data-metheme', 'light')
    self.page.get_by_label('Appearance').select_option('light')
    dialog = self.page.get_by_role('dialog')
    first_number = dialog.locator('.setting-item:has(input[type=number])').first
    before = first_number.locator('input').input_value()
    first_number.get_by_text('Reset to default').click()
    expect(first_number.locator('input')).not_to_have_value(before)

  def test_upload_and_return_to_launcher(self):
    self.page.locator('input[type=file]').set_input_files(
        MODELS / 'test_graph_original.json'
    )
    expect(self.page.get_by_role('table')).to_contain_text('JSON adapter')
    expect(self.page.get_by_role('table')).to_contain_text('Ready to open')
    self.open_models()
    expect(self.page.locator('model-graph-visualizer')).to_be_visible(
        timeout=30000
    )
    self.page.go_back()
    expect(self.page.get_by_role('heading', name='Open models')).to_be_visible()
    expect(self.page.get_by_role('table')).to_contain_text(
        'test_graph_original.json'
    )

  def test_real_adapter_path_and_graph_settings(self):
    self.add_path(MODELS / 'fully_connected.tflite')
    self.page.get_by_role(
        'button', name=re.compile('^Change adapter for')
    ).click()
    self.page.get_by_role(
        'button', name=re.compile('^TFLite adapter \\(Flatbuffer\\)')
    ).click()
    self.open_models()
    expect(self.page.locator('model-graph-visualizer')).to_be_visible(
        timeout=45000
    )
    self.page.get_by_role('button', name='settings', exact=True).click()
    expect(
        self.page.get_by_label(
            'Maximum element count for constant tensor values', exact=True
        )
    ).to_be_visible()
    self.page.get_by_label('Op node label font size', exact=True).fill('12')
    self.page.get_by_role('dialog').get_by_role('button', name='Close').click()
    expect(
        self.page.locator('model-graph-visualizer canvas').first
    ).to_be_visible()

  def test_unsupported_and_failed_model_recovery(self):
    self.add_path('/tmp/unsupported-launcher-test.xyz')
    expect(self.page.get_by_role('table')).to_contain_text('Unsupported format')
    expect(
        self.page.get_by_role('button', name='Open models', exact=True)
    ).to_be_disabled()
    self.page.get_by_role(
        'button', name='Remove unsupported-launcher-test.xyz'
    ).click()
    self.add_path('/tmp/missing-launcher-test.json')
    self.open_models()
    expect(self.page.get_by_role('table')).to_contain_text(
        'Error', timeout=15000
    )
    expect(
        self.page.get_by_role('button', name='Retry', exact=True)
    ).to_be_visible()
    self.page.get_by_role('button', name='Retry', exact=True).click()
    expect(
        self.page.get_by_role('button', name='Retry', exact=True)
    ).to_be_enabled(timeout=15000)
    self.page.get_by_role(
        'button', name='Remove missing-launcher-test.json'
    ).click()
    self.add_path(MODELS / 'test_graph_original.json')
    self.open_models()
    expect(self.page.locator('model-graph-visualizer')).to_be_visible(
        timeout=30000
    )

  def test_batch_failure_preserves_other_rows(self):
    self.add_path(
        str(MODELS / 'test_graph_original.json')
        + ',/tmp/missing-batch-test.json'
    )
    self.open_models()
    expect(self.page.get_by_role('table')).to_contain_text(
        'Error', timeout=15000
    )
    expect(self.page.get_by_role('table')).to_contain_text('Converted')
    expect(
        self.page.get_by_role(
            'checkbox', name='Select test_graph_original.json'
        )
    ).to_be_checked()
    self.open_models()
    expect(self.page.locator('model-graph-visualizer')).to_be_visible(
        timeout=30000
    )

  def test_ten_model_limit_and_narrow_layout(self):
    self.add_path(','.join(f'/tmp/model-{i}.json' for i in range(11)))
    expect(self.page.get_by_role('table').locator('tbody tr')).to_have_count(10)
    expect(
        self.page.get_by_role('button', name='Browse files')
    ).to_be_disabled()
    self.page.get_by_role('button', name='Deselect all').click()
    expect(
        self.page.get_by_role('button', name='Open models', exact=True)
    ).to_be_disabled()
    self.page.set_viewport_size({'width': 390, 'height': 844})
    self.assertTrue(
        self.page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    )
    self.page.get_by_role('button', name='Settings', exact=True).click()
    expect(self.page.get_by_role('dialog')).to_be_visible()
    self.page.keyboard.press('Escape')

  def test_drop_keyboard_and_help(self):
    data = self.page.evaluate_handle(
        """content => {
          const data = new DataTransfer();
          data.items.add(new File([content], 'dropped.json', {type: 'application/json'}));
          return data;
        }""",
        (MODELS / 'test_graph_original.json').read_text(),
    )
    self.page.locator('home-page > .container').dispatch_event(
        'drop', {'dataTransfer': data}
    )
    expect(self.page.get_by_role('table')).to_contain_text('dropped.json')
    button = self.page.get_by_role('button', name='Open model', exact=True)
    button.focus()
    self.page.keyboard.press('Enter')
    expect(self.page.locator('model-graph-visualizer')).to_be_visible(
        timeout=30000
    )
    self.page.go_back()
    self.page.get_by_role('button', name='Help', exact=True).click()
    for name in [
        'Documentation',
        'GitHub',
        'Report an issue or request a feature',
    ]:
      expect(
          self.page.get_by_role('menuitem', name=name, exact=True)
      ).to_have_attribute(
          'href', re.compile('https://github.com/google-ai-edge/model-explorer')
      )
    self.page.get_by_role('menuitem', name='About Model Explorer').click()
    expect(self.page.get_by_role('dialog')).to_contain_text(
        'model graph visualizer'
    )
    self.page.keyboard.press('Escape')
    self.page.get_by_role('button', name='Help', exact=True).click()
    self.page.get_by_role('menuitem', name='Open source libraries').click()
    expect(self.page.get_by_role('dialog')).to_be_visible()

  def test_pte_when_supplied(self):
    path = os.environ.get('MODEL_EXPLORER_PTE_MODEL')
    if not path:
      self.skipTest('Set MODEL_EXPLORER_PTE_MODEL to test a local PTE adapter.')
    self.add_path(path)
    expect(self.page.get_by_role('table')).to_contain_text('PTE Adapter')
    self.open_models()
    expect(self.page.locator('model-graph-visualizer')).to_be_visible(
        timeout=60000
    )
    self.page.go_back()
    self.page.get_by_role('button', name='Remove ' + Path(path).name).click()
    self.page.locator('input[type=file]').set_input_files(path)
    self.open_models()
    expect(self.page.locator('model-graph-visualizer')).to_be_visible(
        timeout=60000
    )


if __name__ == '__main__':
  unittest.main(verbosity=2)
