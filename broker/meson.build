# SPDX-FileCopyrightText: The vmnet-broker authors
# SPDX-License-Identifier: Apache-2.0

vmnet_broker_lib = static_library(
  'vmnet-broker',
  'client.c',
)

vmnet_broker_dep = declare_dependency(
  include_directories: include_directories('.'),
  link_with: vmnet_broker_lib,
)
