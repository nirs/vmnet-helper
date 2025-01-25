# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

project(
  'vmnet-helper',
  'c',
  default_options: [
    'prefix=/opt/vmnet-helper',
    'b_pie=true',
    'buildtype=release',
    'c_std=gnu99',
    'warning_level=3',
  ],
)

version_h = vcs_tag(
  command: ['git', 'describe', '--tags'],
  input: 'version.h.in',
  output: 'version.h',
  fallback: 'devel',
)

version_h_dep = declare_dependency(sources: [version_h])

vmnet_framework = dependency('appleframeworks', modules: 'vmnet', required: true)

vmnet_helper = executable(
  'vmnet-helper',
  'helper.c',
  'options.c',
  install: true,
  dependencies: [
    vmnet_framework,
    version_h_dep,
  ],
)

install_subdir('sudoers.d', install_dir: 'share/doc/vmnet-helper')

test('basic', vmnet_helper)
