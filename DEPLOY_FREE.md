# Grand Line Index Free Deploy

This is the free public preview setup.

## Render one-service deploy

Use Render first. It hosts the Python API and the static frontend in one free web service.

No local Python install is required. If Windows asks for administrator permission to install Python, skip that installer.

1. Create or log in to a GitHub account in the browser.
2. Create a new GitHub repository in the browser.
3. Upload the project files from this folder through GitHub's web upload page.
4. Create or log in to a Render account in the browser.
5. In Render, choose `New` -> `Blueprint`.
6. Select the GitHub repository and use `render.yaml`.
7. Wait for the build to finish.

Render installs Python packages in the cloud from `requirements.txt`, so the local computer does not need admin rights.

The public preview link will look like:

```text
https://grand-line-index.onrender.com/
```

Render may choose another suffix if the name is taken.

## Free-plan notes

- The service can sleep after inactivity.
- The first visit after sleep can be slow.
- Real-time marketplace requests should stay small during testing.
- Do not publish unverified Mercari lowest prices; the app intentionally hides them.
- SNKRDUNK data is restricted to A-grade raw and PSA10 records.
