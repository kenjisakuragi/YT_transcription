---
name: Note Draft Creator
description: A skill to create a formatted draft article on note.com, including text generation and image assets.
---

# Note Draft Creator Skill

This skill allows you to automatically generate a draft article on note.com based on a rough text or topic provided by the user. It handles content structuring, image generation, and automated browser interaction to create the draft in the user's account.

## Requirements

1.  **Python Environment**: Ensure Python is installed.
2.  **Playwright**: Must be installed and browsers downloaded.
    ```bash
    pip install playwright
    playwright install chromium
    ```

## Workflow Steps

### 1. Analyze and Structure Content
Read the user's input (draft text or topic).
- **Title**: Create a catchy, SEO-friendly title.
- **Body**: Structure the content with:
    - Introduction
    - Headings (Use H2 `##` notation)
    - Clear paragraphs
    - Conclusion
- **Visuals**: Decide where images should be placed.

### 2. Generate Assets (Images)
If the article needs a header image or illustrations:
1.  Use the `generate_image` tool.
    - Prompt: Describe the image clearly (e.g., "A modern workspace illustration for a productivity article").
    - ImageName: Use a descriptive name (e.g., `note_header_productivity`).
2.  Note the **absolute path** of the generated image.

### 3. Prepare Data for Automation
Create a JSON object with the article data.
```json
{
  "title": "Your Title Here",
  "body": "## Introduction\n...\n## Point 1\n...",
  "images": ["/absolute/path/to/image.png"]
}
```
Write this JSON to a temporary file, e.g., `temp_note_draft.json`.

### 4. Execute Automation Script
Run the Python script to open the browser and create the draft.

```bash
python skills/note_writer/scripts/post_note.py --content "temp_note_draft.json"
```

**Important**:
- The script uses a persistent browser profile (`chrome_profile` directory).
- **First Run**: The user MUST log in to note.com manually when the browser opens. The script will wait.
- **Subsequent Runs**: Login should be preserved.

### 5. Verification
Confirm with the user that the browser opened and the draft was created. Ask them to review and publish it manually.

## Example Usage

**User Request**: "Create a note draft about 'The benefits of waking up early'."

**Agent Action**:
1.  Draft title: "早起きが人生を変える5つの理由"
2.  Draft body with sections.
3.  Generate image: `early_rising_header`.
4.  Save `draft.json`.
5.  Run `python skills/note_writer/scripts/post_note.py --content draft.json`.

## GitHub Actions Usage

You can run this skill on GitHub Actions to automate draft creation remotely.

### 1. Obtain Authentication State
Run the helper script on your local machine to log in and capture your session cookies.
```bash
python skills/note_writer/scripts/get_note_auth.py
```
This will create a `note_auth.json` file. The content of this file is your "key" to access Note.com without logging in again.

### 2. Set GitHub Secret
1.  Go to your GitHub Repository > **Settings** > **Secrets and variables** > **Actions**.
2.  Create a new repository secret:
    -   **Name**: `NOTE_AUTH_JSON`
    -   **Value**: Copy and paste the entire content of `note_auth.json`.

### 3. Run Workflow
1.  Go to the **Actions** tab in your repository.
2.  Select **note_draft_writer**.
3.  Click **Run workflow**.
4.  Enter the Title and Body of the article, then submit.
5.  The Action will log in using your secret and create the draft.
