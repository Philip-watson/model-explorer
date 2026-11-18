# Copyright 2026 The AI Edge Model Explorer Authors.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy at http://www.apache.org/licenses/LICENSE-2.0
"""Workbench checks against the running UI; uses launcher_smoke_test's env vars.

Run this file for workbench tests only. The launcher suite remains independent.
MODEL_EXPLORER_PTE_MODEL optionally exercises the PTE inspector and tensor data.
"""

import json
import os
from pathlib import Path
import re
import unittest
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect
from launcher_smoke_test import LauncherSmokeTest, MODELS


class WorkbenchSmokeTest(LauncherSmokeTest):
  # Reuse browser/auth/loading helpers, without running the launcher's tests twice.
  def setUp(self):
    super().setUp()
    self.errors = []
    self.page.on('pageerror', lambda error: self.errors.append(str(error)))
    self.page.on(
        'console',
        lambda message: self.errors.append(message.text)
        if message.type == 'error'
        else None,
    )

  def tearDown(self):
    errors = self.errors
    super().tearDown()
    self.assertEqual(errors, [], 'Uncaught browser errors')

  def open_graph(self, path=None):
    self.add_path(path or MODELS / 'test_graph_original.json')
    self.open_models()
    expect(
        self.page.get_by_role('button', name='Fit', exact=True)
    ).to_be_visible(timeout=30000)
    expect(self.page.locator('webgl-renderer canvas').first).to_be_visible()
    self.page.get_by_role('button', name='Fit', exact=True).click()
    self.page.get_by_role('button', name='Zoom in', exact=True).click()
    self.page.get_by_role('button', name='Zoom out', exact=True).click()
    self.search = self.page.get_by_role(
        'textbox', name='Find nodes or layers'
    ).first

  def choose_node(self, name):
    self.search.fill(name)
    result = (
        self.page.locator('search-bar mat-tree-node.leaf')
        .filter(has_text=name)
        .first
    )
    expect(result).to_be_visible()
    result.click(modifiers=['Alt'])
    expect(self.page.locator('info-panel .selection-heading')).to_contain_text(
        name
    )
    self.page.get_by_role(
        'button', name='Clear search', exact=True
    ).first.click()

  def state(self):
    return json.loads(parse_qs(urlparse(self.page.url).query)['data'][0])[
        'uiState'
    ]['paneStates']

  def test_workbench_search_modes(self):
    self.open_graph()
    self.search.fill('root3_n1')
    expect(self.page.locator('search-bar [role=status]')).to_have_text(
        '1 result'
    )
    self.page.get_by_role('combobox', name='Search scope').select_option('all')
    expect(self.page.locator('search-bar [role=status]')).not_to_have_text(
        '1 result'
    )
    self.page.get_by_role('combobox', name='Search scope').select_option(
        'names'
    )
    self.search.fill('[')
    expect(self.page.get_by_role('alert')).not_to_be_visible()
    self.page.get_by_role('checkbox', name='Regex', exact=True).check()
    expect(self.page.get_by_role('alert')).to_contain_text(
        'Invalid regular expression'
    )
    self.search.fill('^root3_n[12]$')
    expect(self.page.locator('search-bar [role=status]')).to_have_text(
        '2 results'
    )
    self.search.press('Escape')
    expect(self.page.locator('.search-results-container')).not_to_be_visible()
    self.search.fill('root1')
    expect(self.page.locator('.search-results-container')).to_be_visible()
    self.page.get_by_role('button', name='Filters', exact=True).click()
    self.page.get_by_role('menuitemcheckbox', name='Attrs', exact=True).click()
    expect(
        self.page.get_by_role('menuitemcheckbox', name='Attrs', exact=True)
    ).to_have_attribute('aria-checked', 'true')
    self.page.keyboard.press('Escape')
    expect(
        self.page.get_by_role('combobox', name='Search scope')
    ).to_have_value('custom')

  def test_workbench_inspector_hide_resize_and_tabs(self):
    self.open_graph()
    self.choose_node('root3_n1')
    tabs = self.page.get_by_role('tablist', name='Inspector sections')
    tabs.get_by_role('tab', name='overview').focus()
    self.page.keyboard.press('ArrowRight')
    expect(
        tabs.get_by_role('tab', name=re.compile('inputs'))
    ).to_have_attribute('aria-selected', 'true')
    expect(self.page.get_by_role('tabpanel')).to_contain_text('root2')
    self.page.keyboard.press('End')
    expect(tabs.get_by_role('tab', name='attributes')).to_be_focused()
    self.page.get_by_role('button', name='Hide inspector', exact=True).click()
    expect(self.page.get_by_role('tablist')).not_to_be_visible()
    expect(
        self.page.get_by_role('button', name='Inspector', exact=True)
    ).to_have_attribute('aria-expanded', 'false')
    self.page.get_by_role('button', name='Inspector', exact=True).click()
    expect(tabs).to_be_visible()
    separator = self.page.get_by_role('separator', name='Resize inspector')
    width = self.page.locator('info-panel').bounding_box()['width']
    separator.focus()
    self.page.keyboard.press('ArrowLeft')
    self.assertAlmostEqual(
        self.page.locator('info-panel').bounding_box()['width'], width + 32
    )
    self.page.keyboard.press('ArrowRight')
    expect(separator).to_have_attribute('aria-valuenow', str(int(width)))
    self.assertAlmostEqual(
        self.page.locator('info-panel').bounding_box()['width'], width
    )
    self.page.get_by_role('button', name='Dock', exact=True).click()
    expect(self.page.get_by_role('dialog')).to_contain_text(
        'not available in this prototype yet'
    )
    self.page.keyboard.press('Escape')
    expect(
        self.page.get_by_role('button', name='Dock', exact=True)
    ).to_be_focused()

  def test_workbench_layers_snapshots_and_exports(self):
    self.open_graph()
    self.choose_node('root3_n1')
    self.page.get_by_role('button', name='Save view', exact=True).click()
    expect(
        self.page.get_by_role('button', name='Restore view 1', exact=True)
    ).to_be_visible()
    self.choose_node('root1')
    self.page.get_by_role('button', name='Restore view 1', exact=True).click()
    expect(self.page.locator('info-panel .selection-heading')).to_contain_text(
        'root3_n1'
    )
    self.page.get_by_role('button', name='Layers', exact=True).click()
    self.page.get_by_role(
        'menuitem', name='Collapse all layers', exact=True
    ).click()
    self.page.wait_for_function(
        'JSON.parse(new'
        " URL(location.href).searchParams.get('data')).uiState.paneStates[0].deepestExpandedGroupNodeIds.length"
        ' === 0'
    )
    self.page.get_by_role('button', name='Layers', exact=True).click()
    self.page.get_by_role(
        'menuitem', name='Expand all layers', exact=True
    ).click()
    self.page.wait_for_function(
        'JSON.parse(new'
        " URL(location.href).searchParams.get('data')).uiState.paneStates[0].deepestExpandedGroupNodeIds.length > 0"
    )
    self.page.get_by_role('button', name='Layers', exact=True).click()
    self.page.get_by_role('menuitemcheckbox', name='Show layer groups').click()
    self.page.wait_for_function(
        'JSON.parse(new'
        " URL(location.href).searchParams.get('data')).uiState.paneStates[0].flattenLayers"
        ' === true'
    )
    self.page.get_by_role('button', name='Layers', exact=True).click()
    self.page.get_by_role('menuitemcheckbox', name='Show layer groups').click()
    self.page.wait_for_function(
        'JSON.parse(new'
        " URL(location.href).searchParams.get('data')).uiState.paneStates[0].flattenLayers"
        ' === false'
    )
    for name in [
        'Graph collection JSON',
        'Current view image (PNG)',
        'Full graph image (PNG)',
    ]:
      self.page.get_by_role('button', name='Export', exact=True).click()
      with self.page.expect_download() as event:
        self.page.get_by_role('menuitem', name=name, exact=True).click()
      content = Path(event.value.path()).read_bytes()
      if name.endswith('JSON'):
        self.assertTrue(json.loads(content))
        self.assertIn(b'root3_n1', content)
      else:
        self.assertTrue(content.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertGreater(len(content), 1000)
    self.page.get_by_role('button', name='Saved view options').click()
    self.page.get_by_role(
        'menuitem', name='Name and manage saved views'
    ).click()
    expect(self.page.get_by_role('dialog')).to_contain_text(
        'nine numbered views'
    )

  def test_workbench_display_data_and_style_controls(self):
    self.open_graph()
    self.page.get_by_role('button', name='Display', exact=True).focus()
    self.page.keyboard.press('Enter')
    popup = self.page.locator('.model-explorer-view-popup')
    expect(popup).to_be_visible()
    option = (
        popup.locator('.show-on-node-item').filter(has_text='Op node id').first
    )
    if not option.count():
      option = popup.locator('.show-on-node-item').first
    before = option.locator('input').is_checked()
    option.click()
    expect(option.locator('input')).to_be_checked(checked=not before)
    self.page.keyboard.press('Escape')
    self.page.get_by_role('button', name='Display', exact=True).click()
    expect(option.locator('input')).to_be_checked(checked=not before)
    self.page.keyboard.press('Escape')
    self.page.get_by_role('button', name='Add data', exact=True).click()
    expect(
        self.page.locator('.model-explorer-node-data-provider-dropdown')
    ).to_contain_text('Node values (JSON)')
    self.page.locator('.upload-per-node-data-input').set_input_files({
        'name': 'workbench-values.json',
        'mimeType': 'application/json',
        'buffer': (
            json.dumps({
                'results': {'root1': {'value': 3}},
                'gradient': [
                    {'stop': 0, 'bgColor': 'white'},
                    {'stop': 1, 'bgColor': 'red'},
                ],
            }).encode()
        ),
    })
    self.page.keyboard.press('Escape')
    expect(self.page.locator('info-panel')).to_contain_text(
        'workbench-values', timeout=15000
    )
    self.page.get_by_role('button', name='Style rules', exact=True).click()
    expect(
        self.page.get_by_role('dialog').get_by_role('button', name='Add rule')
    ).to_be_visible()
    self.page.keyboard.press('Escape')
    self.page.get_by_role('button', name='Edge overlays', exact=True).click()
    expect(
        self.page.locator('.model-explorer-edge-overlays-popup')
    ).to_contain_text('No loaded edge overlays')

  def test_workbench_comparison_and_layout(self):
    self.open_graph()
    self.page.get_by_role('button', name='Compare', exact=True).click()
    expect(self.page.locator('split-pane')).to_have_count(2)
    expect(
        self.page.get_by_role('button', name='Fit', exact=True)
    ).to_have_count(2)
    for index in [0, 1]:
      pane = self.page.locator('split-pane').nth(index)
      pane.get_by_role('button', name='Fit', exact=True).focus()
      expect(self.page.locator('.pane-container').nth(index)).to_have_class(
          re.compile('selected')
      )
      pane.get_by_role('button', name='Hide inspector', exact=True).click()
      expect(
          pane.get_by_role('button', name='Inspector', exact=True)
      ).to_have_attribute('aria-expanded', 'false')
      pane.get_by_role('button', name='Inspector', exact=True).click()
      expect(pane.get_by_role('tablist')).to_be_visible()
    self.page.get_by_role('button', name='Close pane', exact=True).last.click()
    expect(self.page.locator('split-pane')).to_have_count(1)
    for width, height in [(1920, 1080), (1280, 720), (1024, 600)]:
      self.page.set_viewport_size({'width': width, 'height': height})
      footer = self.page.locator('.workbench-status').bounding_box()
      self.assertLessEqual(footer['y'] + footer['height'], height)
      canvas = self.page.locator('webgl-renderer').bounding_box()
      toolbar = self.page.get_by_role('toolbar').bounding_box()
      self.assertGreaterEqual(canvas['y'], toolbar['y'] + toolbar['height'])
      self.assertGreater(canvas['height'], 200)
      for selector in ['title-bar', '.toolbar']:
        self.assertFalse(
            self.page.locator(selector).evaluate(
                'e=>e.scrollWidth>e.clientWidth+1'
            )
        )

  @unittest.skipUnless(
      os.environ.get('MODEL_EXPLORER_PTE_MODEL'), 'Set PTE model path'
  )
  def test_workbench_pte_tensor_details(self):
    self.open_graph(os.environ['MODEL_EXPLORER_PTE_MODEL'])
    self.choose_node('aten::convolution')
    self.page.get_by_role('tab', name='inputs 3', exact=True).click()
    panel = self.page.get_by_role('tabpanel')
    expect(panel).to_contain_text('[1, 3, 32, 32]')
    expect(panel).to_contain_text('[8, 3, 3, 3]')
    panel.evaluate('e=>e.scrollTop=e.scrollHeight')
    last = panel.locator('.flat-item:visible').last.bounding_box()
    bounds = panel.bounding_box()
    self.assertLessEqual(
        last['y'] + last['height'], bounds['y'] + bounds['height']
    )
    self.page.get_by_role('tab', name='outputs 1', exact=True).click()
    expect(panel).to_contain_text('aten::relu')
    expect(panel).to_contain_text('[1, 8, 32, 32]')
    self.page.get_by_role('tab', name='attributes', exact=True).click()
    expect(panel).to_contain_text('KernelCall')
    self.page.get_by_role(
        'button', name='Trace connections', exact=True
    ).click()
    expect(
        self.page.get_by_role('button', name='Stop tracing', exact=True)
    ).to_have_attribute('aria-pressed', 'true')
    self.page.get_by_role('button', name='Stop tracing', exact=True).click()
    expect(
        self.page.get_by_role('button', name='Trace connections', exact=True)
    ).to_have_attribute('aria-pressed', 'false')


if __name__ == '__main__':
  suite = unittest.TestSuite(
      WorkbenchSmokeTest(name)
      for name in unittest.defaultTestLoader.getTestCaseNames(
          WorkbenchSmokeTest
      )
      if name.startswith('test_workbench_')
  )
  result = unittest.TextTestRunner(verbosity=2).run(suite)
  raise SystemExit(not result.wasSuccessful())
