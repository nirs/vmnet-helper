# Project Rules

## Before making code changes

- Discuss the design with the user
- Show example changes to make sure we are in the right direction
- If the user request is not clear, ask for more details
- List possible alternatives to make the change

## Making code changes

- Do the minimal change needed, no extra code that is not needed right now
- Keep changes small to make human review easy and avoid mistakes
- Update documentation if needed
- Avoid unrelated changes (spelling, whitespace, etc.)

## Building

- Use `./build.sh buid-dir` to build a release tarball
- Use `meson compile -C build/{arch}` for quick build for current architecture
- Never use direct `clang` commands that would create `.o` or `.d` files in the source directory

## File organization

- Keep files focused - separate files for different concerns
- All files need SPDX license headers - check existing files for the format

## Error handling

- Check existing code for error handling conventions

## Commit messages

When the user wants to commit changes, suggest a commit message.

The main purpose is to explain why the change was made - what are we trying to do.

Content guidelines:
- Explain how the change affects the user - what is the new or modified behavior
- If the change affects performance, include measurements and description of how we measured
- If the change modifies the output, include example output with and without the change
- If the change introduces new logs, show example logs including the changed or new logs
- If several alternatives were considered, explain why we chose the particular solution
- Discuss the negative effects of the change if any
- If the change includes new APIs, describe the new APIs and how they are used
- Avoid describing details that are best seen in the diff
