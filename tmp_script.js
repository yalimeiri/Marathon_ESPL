
    document.addEventListener("DOMContentLoaded", function () {
        const videoZoomContainer = document.getElementById("video-zoom-container");
        const videoZoomWrapper = document.getElementById("video-zoom-wrapper");
        const dragOverlay = document.getElementById("video-drag-overlay");

        if (videoZoomWrapper && dragOverlay) {
            let currentScale = 1;
            let isDragging = false;
            let startX, startY, translateX = 0, translateY = 0;

            const btnZoomIn = document.getElementById("btn-zoom-in");
            const btnZoomOut = document.getElementById("btn-zoom-out");
            const btnZoomReset = document.getElementById("btn-zoom-reset");
            const btnFullscreen = document.getElementById("btn-custom-fullscreen");

            function updateTransform() {
                // If returning to normal, reset translation
                if (currentScale <= 1) {
                    currentScale = 1;
                    translateX = 0;
                    translateY = 0;
                }

                videoZoomWrapper.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentScale})`;

                if (currentScale > 1) {
                    dragOverlay.style.cursor = isDragging ? "grabbing" : "grab";
                } else {
                    dragOverlay.style.cursor = "default";
                }
            }

            if (btnZoomIn) {
                btnZoomIn.addEventListener("click", () => {
                    currentScale = Math.min(currentScale + 0.5, 4);
                    updateTransform();
                });
            }

            if (btnZoomOut) {
                btnZoomOut.addEventListener("click", () => {
                    currentScale = Math.max(currentScale - 0.5, 1);
                    updateTransform();
                });
            }

            if (btnZoomReset) {
                btnZoomReset.addEventListener("click", () => {
                    currentScale = 1;
                    updateTransform();
                });
            }

            // Custom Fullscreen Handler
            function toggleFullscreen() {
                if (!document.fullscreenElement) {
                    if (videoZoomContainer.requestFullscreen) {
                        videoZoomContainer.requestFullscreen();
                    } else if (videoZoomContainer.webkitRequestFullscreen) { /* Safari */
                        videoZoomContainer.webkitRequestFullscreen();
                    } else if (videoZoomContainer.msRequestFullscreen) { /* IE11 */
                        videoZoomContainer.msRequestFullscreen();
                    }
                } else {
                    if (document.exitFullscreen) {
                        document.exitFullscreen();
                    } else if (document.webkitExitFullscreen) { /* Safari */
                        document.webkitExitFullscreen();
                    } else if (document.msExitFullscreen) { /* IE11 */
                        document.msExitFullscreen();
                    }
                }
            }

            if (btnFullscreen) {
                btnFullscreen.addEventListener("click", toggleFullscreen);
            }

            // Double click to toggle fullscreen
            dragOverlay.addEventListener("dblclick", (e) => {
                e.preventDefault();
                toggleFullscreen();
            });

            // Dragging Logic
            let clickStartX = 0, clickStartY = 0;

            dragOverlay.addEventListener("mousedown", (e) => {
                clickStartX = e.clientX;
                clickStartY = e.clientY;

                // Only allow dragging if zoomed in
                if (currentScale > 1) {
                    isDragging = true;
                    // Keep track of where we click relative to the current translation
                    startX = e.clientX - translateX;
                    startY = e.clientY - translateY;
                    dragOverlay.style.cursor = "grabbing";

                    // Temporarily remove transition for instant 1:1 dragging mapping
                    videoZoomWrapper.style.transition = "none";
                }
            });

            window.addEventListener("mousemove", (e) => {
                if (!isDragging) return;
                e.preventDefault();
                translateX = e.clientX - startX;
                translateY = e.clientY - startY;

                videoZoomWrapper.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentScale})`;
            });

            dragOverlay.addEventListener("mouseup", (e) => {
                // Distinguish between a drag and a simple click
                const dist = Math.hypot(e.clientX - clickStartX, e.clientY - clickStartY);

                // If it's a simple click (not a drag), toggle play/pause
                if (dist < 5) {
                    const videoElement = document.getElementById("main-video-player");
                    if (videoElement) {
                        if (videoElement.paused || videoElement.ended) {
                            videoElement.play();
                        } else {
                            videoElement.pause();
                        }
                    }
                }
            });

            window.addEventListener("mouseup", () => {
                if (isDragging) {
                    isDragging = false;
                    // Restore cursor appropriately
                    dragOverlay.style.cursor = currentScale > 1 ? "grab" : "default";
                    // Restore smooth transition for the buttons
                    videoZoomWrapper.style.transition = "transform 0.2s ease-out";
                }
            });

            // Handle mouse leaving the window while dragging
            window.addEventListener("mouseleave", () => {
                if (isDragging) {
                    isDragging = false;
                    dragOverlay.style.cursor = "grab";
                    videoZoomWrapper.style.transition = "transform 0.2s ease-out";
                }
            });

            // Wheel / Trackpad Zooming inside video
            dragOverlay.addEventListener("wheel", (e) => {
                e.preventDefault(); // Prevent page scrolling

                const zoomSpeed = 0.1;
                // e.deltaY > 0 is scrolling down (zoom out), e.deltaY < 0 is scrolling up (zoom in)
                if (e.deltaY < 0) {
                    currentScale = Math.min(currentScale + zoomSpeed, 4);
                } else {
                    currentScale = Math.max(currentScale - zoomSpeed, 1);
                }
                updateTransform();
            }, { passive: false });
        }

        // Global Keyboard Controls for Video Playback
        const videoElement = document.getElementById("main-video-player");
        if (videoElement) {
            // Setup Custom Controls
            const playBtn = document.getElementById("ctrl-playpause");
            const timeDisplay = document.getElementById("ctrl-time");
            const progressBar = document.getElementById("ctrl-progress");
            const volBtn = document.getElementById("ctrl-volume");
            const volSlider = document.getElementById("ctrl-vol-slider");
            const speedSelect = document.getElementById("ctrl-speed");
            const controlsContainer = document.getElementById("custom-video-controls");
            const zoomToolbar = document.getElementById("custom-zoom-toolbar");
            const videoZoomContainer = document.getElementById("video-zoom-container");

            if (playBtn) {
                function formatTime(seconds) {
                    if (isNaN(seconds) || !isFinite(seconds)) return "0:00";
                    const h = Math.floor(seconds / 3600);
                    const m = Math.floor((seconds % 3600) / 60);
                    const s = Math.floor(seconds % 60);

                    if (h > 0) {
                        return h + ':' + (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
                    }
                    return m + ':' + (s < 10 ? '0' : '') + s;
                }

                const updateMaxTime = () => {
                    if (isFinite(videoElement.duration)) {
                        progressBar.max = videoElement.duration;
                        timeDisplay.textContent = formatTime(videoElement.currentTime) + ' / ' + formatTime(videoElement.duration);
                    }
                };

                if (videoElement.readyState >= 1) {
                    updateMaxTime();
                }
                videoElement.addEventListener('loadedmetadata', updateMaxTime);
                videoElement.addEventListener('durationchange', updateMaxTime);

                videoElement.addEventListener('timeupdate', () => {
                    if (!progressBar.dragging) {
                        progressBar.value = videoElement.currentTime;
                        timeDisplay.textContent = formatTime(videoElement.currentTime) + ' / ' + formatTime(videoElement.duration);
                    }
                });

                progressBar.addEventListener('input', () => {
                    progressBar.dragging = true;
                    timeDisplay.textContent = formatTime(progressBar.value) + ' / ' + formatTime(videoElement.duration);
                });

                progressBar.addEventListener('change', () => {
                    videoElement.currentTime = progressBar.value;
                    progressBar.dragging = false;
                });

                playBtn.addEventListener('click', () => {
                    if (videoElement.paused || videoElement.ended) videoElement.play();
                    else videoElement.pause();
                });

                videoElement.addEventListener('play', () => playBtn.textContent = "⏸");
                videoElement.addEventListener('pause', () => playBtn.textContent = "▶");
                videoElement.addEventListener('volumechange', () => updateVolIcon());
                videoElement.addEventListener('speedchange', () => updateSpeedIcon());
                volSlider.addEventListener('input', () => {
                    videoElement.volume = volSlider.value;
                    videoElement.muted = (videoElement.volume === 0);
                    updateVolIcon();
                });

                volBtn.addEventListener('click', () => {
                    videoElement.muted = !videoElement.muted;
                    if (!videoElement.muted && videoElement.volume === 0) {
                        videoElement.volume = 1;
                        volSlider.value = 1;
                    }
                    updateVolIcon();
                });

                if (speedSelect) {
                    speedSelect.addEventListener('change', () => {
                        videoElement.playbackRate = parseFloat(speedSelect.value);
                    });
                }

                function updateVolIcon() {
                    if (videoElement.muted || videoElement.volume === 0) volBtn.textContent = '🔇';
                    else if (videoElement.volume < 0.5) volBtn.textContent = '🔉';
                    else volBtn.textContent = '🔊';
                }

                // Controls visibility logic (hide after 2.5s)
                let controlTimeout;
                function showControls() {
                    controlsContainer.style.opacity = '1';
                    zoomToolbar.style.opacity = '1';
                    zoomToolbar.style.pointerEvents = 'auto';
                    videoZoomContainer.style.cursor = 'default';
                    clearTimeout(controlTimeout);
                    if (!videoElement.paused) {
                        controlTimeout = setTimeout(() => {
                            controlsContainer.style.opacity = '0';
                            zoomToolbar.style.opacity = '0';
                            zoomToolbar.style.pointerEvents = 'none';
                            if (document.fullscreenElement) {
                                videoZoomContainer.style.cursor = 'none'; // hide cursor in fullscreen when inactive
                            }
                        }, 2500);
                    }
                }

                videoZoomContainer.addEventListener('mousemove', showControls);
                videoZoomContainer.addEventListener('mouseleave', () => {
                    if (!videoElement.paused) {
                        controlsContainer.style.opacity = '0';
                        zoomToolbar.style.opacity = '0';
                        zoomToolbar.style.pointerEvents = 'none';
                    }
                });
                videoElement.addEventListener('pause', showControls);
                // Also trigger initially
                showControls();
            }

            window.addEventListener("keydown", (e) => {
                // Ignore keys if the user is typing in an input field (e.g., search or comments)
                if (document.activeElement.tagName === "INPUT" || document.activeElement.tagName === "TEXTAREA") {
                    return;
                }

                switch (e.code) {
                    case "Space":
                        // Prevent the spacebar from scrolling down the page
                        e.preventDefault();
                        if (videoElement.paused || videoElement.ended) {
                            videoElement.play();
                        } else {
                            videoElement.pause();
                        }
                        break;
                    case "ArrowRight":
                        e.preventDefault();
                        videoElement.currentTime += 5;
                        break;
                    case "ArrowLeft":
                        e.preventDefault();
                        videoElement.currentTime -= 5;
                        break;
                }
            });
        }
    });
