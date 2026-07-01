---
name: x-md
description: Archive a given X or Twitter post link into an Obsidian-ready Markdown note using the local x-md CLI. Use when the user asks to scrape, archive, save, capture, or export an X link, X post, Twitter post, or Twitter thread to Markdown for local notes.
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

5. Rename the generated `<slug>.md` file (it lands directly in the output directory, not in a per-post subfolder) into an Obsidian-friendly note name:

   ```text
   YYYYMMDD - <DisplayTitle>.md
   ```

   - Use the source post date from `published` for `YYYYMMDD`.
   - Use a short content-facing display title.
   - Default display title: `<AuthorDisplayName> post <N>`, using the author's display name from frontmatter before the `@handle`.
   - Start at `post 1`; if a note with that name already exists in the output directory, increment the number until the name is unique.

6. Add a `title` field to the note's frontmatter, as the first key, matching the display title:

   ```markdown
   ---
   title: "Serenity post 1"
   source: "https://x.com/serenity/status/123"
   author:
     - "@serenity"
   published: 2026-06-30
   created: 2026-07-01
   ---
   ```

   - Do not rewrite post text, quote text, reply text, or the first `#` header beyond the title and asset-link cleanup below.

7. Confirm image links in the note point to `raw/assets/<filename>` (the script writes them this way already; only fix them if something is off).

8. Report the final note path and the shared `raw/assets/` directory it draws images from.

## Output

The archive writes one flat Markdown file directly into the output directory (not wrapped in a per-post subfolder), plus any images into a single shared `raw/assets/` directory next to it:

- `<slug>.md`
- `raw/assets/` with local image files from every archived post, named `<post_id>-<n>.<ext>` so they never collide across posts

Keeping each post as its own uniquely-named file (instead of a same-named `index.md` inside a folder) is what keeps Obsidian's graph view legible — every node gets a distinct label instead of all showing up as "Index".

The archive includes:

- the input post
- the quoted-post chain
- the input author's own direct-reply continuation chain (a self-thread used to post long text), merged into the Post section as one continuous piece rather than listed as replies
- any remaining reply paths that end at comments by the input author, trimmed to start after the continuation chain

In the rendered Replies section, each reply path should start at the first actual reply beneath the input post (or beneath the end of its self-thread continuation) rather than repeating earlier posts again.

## Operational Notes

- Google Chrome must be logged into X before running the command.
- The scraper uses Chrome cookies through `gallery-dl`.
- If extraction fails with an X, cookie, or auth error, surface the exact error and suggest logging into X again in Chrome.
- If extraction fails with DNS or network errors, mention the exact network symptom before retrying.
- Only post-process the generated Markdown for the `title` frontmatter field, file renaming, and local asset links unless the user explicitly asks for another formatting fix.
