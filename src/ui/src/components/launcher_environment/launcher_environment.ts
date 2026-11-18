/**
 * @license
 * Copyright 2026 The Model Explorer Authors. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ==============================================================================
 */

import {Component, computed, inject} from '@angular/core';
import {MatButtonModule} from '@angular/material/button';
import {MatDialog} from '@angular/material/dialog';
import {MatIconModule} from '@angular/material/icon';
import {AdapterExtension, ExtensionType} from '../../common/types';
import {ExtensionService} from '../../services/extension_service';
import {PrototypeFeatureDialog} from '../prototype_feature_dialog/prototype_feature_dialog';

// Concise launcher copy; keep the registry descriptions for model details.
const ADAPTER_SUMMARIES: Readonly<Record<string, string>> = {
  builtin_tflite_flatbuffer: 'Reads the original TFLite graph.',
  builtin_tflite_mlir: 'Converts TFLite through MLIR.',
  builtin_tf_mlir: 'Converts TensorFlow SavedModels through MLIR.',
  builtin_tf_direct: 'Reads TensorFlow SavedModels directly.',
  builtin_graphdef: 'Opens TensorFlow GraphDef graphs.',
  builtin_pytorch_exportedprogram: 'Opens exported PyTorch programs.',
  builtin_mlir: 'Opens MLIR text or bytecode.',
  builtin_hfgraph:
    'Shows model structure and source logic. Running .hfrun requires the hfgraph extra.',
  builtin_json: 'Opens Model Explorer graphs or TensorFlow.js models.',
};

/** Read-only environment information from the existing extension registry. */
@Component({
  selector: 'launcher-environment',
  standalone: true,
  imports: [MatButtonModule, MatIconModule],
  templateUrl: './launcher_environment.ng.html',
  styleUrls: ['./launcher_environment.scss'],
})
export class LauncherEnvironment {
  readonly extensions = inject(ExtensionService);
  private readonly dialog = inject(MatDialog);
  readonly accessAddress = window.location.host;
  readonly adapters = computed(() => {
    if (this.extensions.loading()) return [];
    return this.extensions.extensions.filter(
      (ext): ext is AdapterExtension => ext.type === ExtensionType.ADAPTER,
    );
  });
  readonly customAdapters = computed(() =>
    this.adapters().filter((ext) => !ext.id.startsWith('builtin_')),
  );
  readonly additionalAdapters = computed(() => {
    const previewAdapters = this.customAdapters().slice(0, 3);
    return this.adapters().filter((ext) => !previewAdapters.includes(ext));
  });
  readonly providers = computed(() => {
    if (this.extensions.loading()) return [];
    return this.extensions
      .getCustomExtensions()
      .filter((ext) => ext.type === ExtensionType.NODE_DATA_PROVIDER);
  });
  readonly formats = computed(() => [
    ...new Set([
      ...this.customAdapters().flatMap((ext) => ext.fileExts),
      ...this.adapters().flatMap((ext) => ext.fileExts),
    ]),
  ]);

  getAdapterSummary(adapter: AdapterExtension): string {
    return ADAPTER_SUMMARIES[adapter.id] ?? adapter.description;
  }

  showPrototypeFeature(feature: 'extensions' | 'diagnostics') {
    this.dialog.open(PrototypeFeatureDialog, {
      width: '480px',
      data:
        feature === 'extensions'
          ? {
              title: 'Manage extensions',
              description:
                'Installing and configuring extensions here is being explored. Your currently loaded extensions are unchanged.',
            }
          : {
              title: 'Server diagnostics',
              description:
                'Server logs and launch details are being explored. Model-loading errors remain available in Model details.',
            },
    });
  }
}
