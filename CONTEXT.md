# MarathonLMS Architecture & Context Guide

This document is designed to provide future LLMs with the complete, up-to-date context of the MarathonLMS Django application. It summarizes all critical architectural decisions, security features, deployment quirks, and data flows.

---

## 🏗️ Core Architecture & Stack
- **Framework:** Django 5.x
- **Database:** SQLite (Local Dev) -> PostgreSQL (Production via Railway.app)
- **Deployment:** Railway.app (via GitHub push). Uses `gunicorn`, `whitenoise` for static files.
- **Python Version:** 3.12+ 

---

## 🔐 Security & Access Control

### 1. Strict Device Lock ("First Device Wins")
- **Goal:** Prevent account sharing by binding a user to the exact device and browser they first log in with.
- **Implementation:**
  - `accounts/models.py`: Custom `CustomUser` model includes a `device_uuid` field.
  - `accounts/signals.py`: On `user_logged_in`, if `device_uuid` is null, generate a random UUID and lock it to the user.
  - `middleware/single_device.py`: Validates every request. If the user's signed cookie `device_token` doesn't match the database `device_uuid`, they are force-logged out with an explicit error message (`messages.error`).
- **Admin Override:** Superusers/staff bypass this lock. Admins can manually click "Reset device lock" in the Django Admin user list to clear the UUID and allow the user to register a new device.

### 2. Video Download Prevention
- Cloudinary MP4 `<video>` tags are protected using:
  - `controlsList="nodownload"` (hides native download button)
  - `oncontextmenu="return false;"` (disables right-click to save)
  - A transparent CSS `div` overlaid over the video (leaving the bottom 60px for controls) to absorb clicks and block "enable right-click" browser extensions.

---

## 📹 Video Hosting & Playback

The platform supports multiple video sources handled transparently by the template (`templates/courses/video_detail.html`):

### 1. Cloudinary (Primary Method)
- **Why:** Bypasses Railway's strict 30s timeout and payload limits (Error 413) for large media uploads.
- **How:** The Django Admin `Video` change form was overridden (`templates/admin/courses/video/change_form.html`).
- **Integration:** It injects a custom Javascript Cloudinary Widget directly beneath the standard fields. When the admin clicks "Upload Video via Cloudinary", the file goes *directly* from the browser to Cloudinary in 6MB chunks, bypassing the Django server entirely. Upon success, JS automatically populates the `cloudinary_url` and `public_id` fields for saving. 
- **Auto-Play:** Cloudinary videos utilize the HTML5 `ended` event listener via JS to automatically redirect the user to the next video in the playlist.

### 2. YouTube
- Automatically parses `watch?v=`, `youtu.be/`, and `/embed/` links.
- **Restriction:** Videos from Google Workspace (enterprise/edu) accounts often block external iframe embedding. The site owner must upload to standard `@gmail.com` YouTube accounts as "Unlisted".

### 3. Google Drive
- Automatically reformats links to `/preview?embedded=true`.
- Includes extensive iframe sandboxing to prevent CORS blocks.
- **Drawback:** Due to third-party cookie restrictions, some browsers show a black screen. Users must use the pop-out arrow to view the video. Auto-play (`ended` event) does not work with Google Drive iframes due to cross-origin security.

---

## 🎨 UI & Frontend Design
- **Styling:** Primarily inline HTML styles and Vanilla CSS with a dark-mode aesthetic (slate/indigo/violet accents).
- **Video Player Layout:** The video player screen uses a modern CSS Grid layout (1fr 350px). The main video is on the left, and a sticky, scrollable sidebar "Playlist" is on the right, highlighting the active video.

---

## 🚀 Deployment Logistics (Railway.app)
- We rely on environment variables (`python-decouple`) heavily.
- `DATABASE_URL`: Injected automatically by Railway Postgres.
- `CLOUDINARY_CLOUD_NAME`: Needed by the frontend JS widget in the admin.
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`: Set manually in the Railway variables dashboard. 
- **Important:** If static files are failing to load, ensure `whitenoise.runserver_nostatic` is above `staticfiles` in `INSTALLED_APPS` and `WhiteNoiseMiddleware` is directly under `SecurityMiddleware`.
