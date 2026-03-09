/**
 * auto_save_sortable.js
 * 
 * Automatically clicks "Save and continue editing" when a sortable row stops dragging.
 * This provides the illusion of instantaneous AJAX saves for Inline Django Admin fields.
 */

document.addEventListener("DOMContentLoaded", function () {
    // We bind to the document and listen for the custom sortupdate event fired by adminsortable2.
    // jQuery is usually available in Django admin by default via django.jQuery or $
    
    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('sortupdate', function(e, ui) {
            console.log("Drag-and-drop sort triggered! Auto-saving...");

            // Find the "Save and continue editing" button
            var saveBtn = document.querySelector('input[name="_continue"]');
            
            if (saveBtn) {
                // Blur active elements to prevent conflict
                if (document.activeElement) {
                    document.activeElement.blur();
                }

                // Briefly change the button text so the admin knows it's auto-saving
                saveBtn.value = "Saving Order...";
                saveBtn.style.opacity = "0.7";
                saveBtn.style.pointerEvents = "none";
                
                // Click the button to POST the form immediately
                saveBtn.click();
            } else {
                console.warn("Auto-save failed: '_continue' button not found on this admin page.");
            }
        });
    }
});
