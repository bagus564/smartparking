
console.log("yang YTTA YTTA aja")

// transfer datepicker into readonly input box
document.addEventListener("DOMContentLoaded", function(){
    const datePickerInput = document.getElementById("default-datepicker")
    const readOnlyInput = document.getElementById("default-date")

    // 🔥 PERBAIKAN: Hanya jalankan event listener jika kedua elemen ditemukan.
    if (datePickerInput && readOnlyInput) { 
        datePickerInput.addEventListener("changeDate", function(event){
            readOnlyInput.value = event.target.value
        })

        datePickerInput.addEventListener("change", function(){
            readOnlyInput.value = datePickerInput.value
        })
    }
});

/*
// Bagian yang dikomentari diabaikan dalam perbaikan ini.
*/

// previewing car image
console.log("JS file is loaded")
document.addEventListener('DOMContentLoaded', function () {
    const imageInput = document.getElementById('imageUpload');
    const preview = document.getElementById('preview_image');

    // 🔥 PERBAIKAN: Hanya jalankan logika upload jika kedua elemen ditemukan.
    // Jika tidak ada, script akan berhenti di sini tanpa crash, mengatasi error Console.
    if (!imageInput || !preview) { 
        console.error("❌ Skipping image upload logic: Required elements not found.");
        return;
    }

    // Jika elemen ditemukan, tambahkan event listener
    imageInput.addEventListener('change', function (event) {
        console.log("📷 File input changed");
        const file = event.target.files[0];

        if (!file) {
            console.warn("⚠️ No file selected.");
            return;
        }

        console.log("✅ File selected:", file.name);

        const reader = new FileReader();

        reader.onload = function (e) {
            console.log("📄 FileReader result:", e.target.result.slice(0, 100) + "...");
            preview.src = e.target.result;
            preview.classList.remove('hidden');
            console.log("🖼️ Preview image updated.");
        };

        reader.onerror = function () {
            console.error("❌ Error reading file.");
        };

        reader.readAsDataURL(file);
        console.log("📤 Reading file as data URL...");
    });
});

// countdown and status on history
function formatTime(ms) {
    const totalSec = Math.max(0, Math.floor(ms / 1000));
    const hours = Math.floor(totalSec / 3600).toString().padStart(2, '0');
    const minutes = Math.floor((totalSec % 3600) / 60).toString().padStart(2, '0');
    const seconds = (totalSec % 60).toString().padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
}

function updateCountdown() {
    const now = new Date();

    document.querySelectorAll('.countdown').forEach(span => {
        const start = new Date(span.dataset.start);
        const end = new Date(span.dataset.end);
        const statusSpan = span.closest('tr').querySelector('.status');

        let countdownTime;
        let statusText;

        if (now < start) {
            countdownTime = end - start;
            statusText = 'Reserved';
        } else if (now >= start && now <= end) {
            countdownTime = end - now;
            const diffMin = Math.floor((end - now) / 60000);
            statusText = diffMin <= 30 ? 'About to end' : 'Placed';
        } else {
            countdownTime = 0;
            statusText = 'Finished';
        }

        span.textContent = formatTime(countdownTime);
        if (statusSpan) statusSpan.textContent = statusText;
    });
}

setInterval(updateCountdown, 1000);
document.addEventListener('DOMContentLoaded', updateCountdown);