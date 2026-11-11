// 1. Character count logic
const textarea = document.getElementById('message');
const charCount = document.getElementById('charCount');

if (textarea && charCount) {
    textarea.addEventListener('input', function() {
        charCount.textContent = `${this.value.length}/500 characters`;
        if (this.value.length >= 500) {
            charCount.style.color = 'red';
        } else {
            charCount.style.color = '';
        }
    });
}

// 2. Form Submission logic
const contactForm = document.querySelector('form');
if (contactForm) {
    contactForm.addEventListener('submit', function(e) {
        // Sirf loading dikhaye ga, submit hone par page refresh ho jaye ga
        Swal.fire({
            title: 'Sending Message...',
            text: 'Connecting to PharmaHub servers',
            icon: 'info',
            showConfirmButton: false,
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading()
            }
        });
    });
}