---
name: x-md
description: Archive a given X or Twitter post link into an Obsidian-ready Markdown folder using the local x-md CLI. Use when the user asks to scrape, archive, save, capture, or export an X link, X post, Twitter post, or Twitter thread to Markdown for local notes.
---

# X Markdown Archiver

Use the bundled `x-md` CLI in this skill repo to archive a given X or Twitter post into the Obsidian inbox.

## Workflow

1. Use this repo as the working directory:

   ```sh
   /Users/guodawei/Documents/GitHub/x-md-skill
   ```

2. Check whether the project virtualenv exists:

   ```sh
   test -x .venv/bin/python
   ```

   If it does not exist, initialize it:

   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install -r scripts/requirements.txt
   ```

3. Archive the X link into the Obsidian inbox:

   ```sh
   .venv/bin/python scripts/archive_x_post.py archive "<X_POST_URL>" --out "/Users/guodawei/Library/Mobile Documents/com~apple~CloudDocs/Documents/Obsidian Vault/inbox"
   ```

4. If the user gives special instructions in their prompt, follow those instructions over the default naming or post-processing rules below.

5. Rename the generated archive folder into an Obsidian-friendly folder-note name:

   ```text
   YYYYMMDD - <DisplayTitle>
   ```

   - Use the source post date from `created_at` for `YYYYMMDD`.
   - Use a short content-facing display title, not `Index`.
   - Default display title: `<AuthorDisplayName> post <N>`, using the author's display name from frontmatter before the `@handle`.
   - Start at `post 1`; if that folder already exists, increment the number until the name is unique.
   - Keep the Markdown file itself named `index.md` so local assets and folder-note behavior remain stable.

6. Update `index.md` metadata title to match the display title, but keep the first header as `Index`:

   ```markdown
   ---
   title: "Serenity post 1"
   ...
   ---

   # Index
   ```

   - Use the content-facing display title, not `Index`, for the `title` field.
   - Keep the first `#` header as `Index`.
   - Do not rewrite post text, quote text, or reply text beyond the title and asset-link cleanup below.

7. If image files are stored under `assets/`, ensure Markdown image links point to `assets/<filename>` rather than bare filenames.

8. Report the final archive folder path and its `index.md` path.

## Output

The archive creates one folder containing:

- `index.md`
- `assets/` with local image files

The archive includes:

- the input post
- the quoted-post chain
- reply paths that end at comments by the input author

In the rendered Replies section, each reply path should start at the first actual reply beneath the input post rather than repeating the input post again.

## Operational Notes

- Google Chrome must be logged into X before running the command.
- The scraper uses Chrome cookies through `gallery-dl`.
- If extraction fails with an X, cookie, or auth error, surface the exact error and suggest logging into X again in Chrome.
- If extraction fails with DNS or network errors, mention the exact network symptom before retrying.
- Only post-process the generated Markdown for the `title` frontmatter field, first `#` header, folder renaming, and local asset links unless the user explicitly asks for another formatting fix.
