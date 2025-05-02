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

config = configuration_data()
config.set('PREFIX', get_option('prefix'))
configure_file(input: 'config.h.in', output: 'config.h', configuration: config)

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

vmnet_client = executable(
  'vmnet-client',
  'client.c',
  install: true,
  dependencies: [
    version_h_dep,
  ],
)

install_subdir('sudoers.d', install_dir: 'share/doc/vmnet-helper')

# Disable useless options when testing with external commands.
plain_env = environment(
  {
    'MALLOC_PERTURB_': '0',
    'UBSAN_OPTIONS': '0',
    'ASAN_OPTIONS': '0',
    'MSAN_OPTIONS': '0',
  },
)

# codespell test works only in git repo since we depend on git to list the files.
# The test is skipped if codespell is not installed.
fs = import('fs')
if fs.is_dir('.git')
  codespell = find_program('codespell', required: false)
  if codespell.found()
    files_to_check = []
    r = run_command('git', 'ls-files', check: true)
    foreach name : r.stdout().strip().split()
      if not name.startswith('performance')
        files_to_check += name
      endif
    endforeach
    test(
      'codespell', codespell,
      args: files_to_check,
      env: plain_env,
      verbose: true,
      workdir: meson.project_source_root(),
    )
  endif
endif
