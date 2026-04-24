# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

vmnet_helper = executable(
  'vmnet-helper',
  'helper.c',
  'options.c',
  'os.c',
  install: true,
  dependencies: [
    corefoundation,
    vmnet_framework,
    vmnet_broker_dep,
    version_h_dep,
  ],
)

vmnet_run = executable(
  'vmnet-run',
  'run.c',
  'os.c',
  install: true,
  dependencies: [
    version_h_dep,
  ],
)
