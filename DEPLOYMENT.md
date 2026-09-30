# Deployment

1. Push the contents of this folder to the root of the GitHub repository.
2. In Render choose New → Blueprint and connect the repository.
3. Render reads `render.yaml` from the repo root.
4. Enter a strong `ADMIN_PASSWORD` when prompted.
5. Deploy.
6. Open `/` for the terminal. Health: `/api/health`. Diagnostics: `/api/diagnostics` after login.

Do not upload the ZIP as the repository source. The repository itself should contain `render.yaml`, `backend/`, and `frontend/`.
