# SPDX-FileCopyrightText: The vmnet-helper authors
# SPDX-License-Identifier: Apache-2.0

project(
  'vmnet-helper',
  'c',
  default_options: [
    # /opt/vmnet-helper is the canonical install path for the upstream
    # release, required by sudoers rules on macOS < 26. Override with
    # --prefix for other installations (e.g. Homebrew).
    'prefix=/opt/vmnet-helper',
    'b_pie=true',
    'buildtype=release',
    'c_std=gnu99',
    'warning_level=3',
  ],
)

gen_version = find_program('building/gen-version')
version_h = custom_target(
  'version.h',
  output: 'version.h',
  command: [gen_version, '@OUTPUT@', meson.project_source_root()],
  # Run on every build, but gen-version only updates the file when the
  # version or commit changes, avoiding unnecessary rebuilds.
  build_always_stale: true,
)

version_h_dep = declare_dependency(sources: [version_h])

subdir('broker')

vmnet_framework = dependency('appleframeworks', modules: 'vmnet', required: true)
corefoundation = dependency('appleframeworks', modules: 'CoreFoundation', required: true)

subdir('programs')

# Sudoers rule and documentation, used by install.sh to configure sudo
# for running vmnet-helper without a password on macOS < 26.
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
