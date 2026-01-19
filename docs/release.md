<!--
SPDX-FileCopyrightText: The vmnet-helper authors
SPDX-License-Identifier: Apache-2.0
-->

# How to create a release

To create a release, create a tag from the branch to be released and push the
tag to github:

```console
git checkout release-branch
git tag v1.2.3
git push origin v1.2.3
```

Pushing the tag trigger the [release workflow](.github/workflow/release.yaml),
building the assets and creating the release draft.

The draft can be inspected and edited as needed before publishing the release.

After the release is published it cannot be modified, since we use [imutable
releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases).
