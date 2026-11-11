
//1st
  const ctaObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        // Title, text, buttons
        document.querySelector("#ctaTitle").classList.remove("opacity-0","translate-y-6");
        document.querySelector("#ctaText").classList.remove("opacity-0","translate-y-6");
        document.querySelector("#ctaBtns").classList.remove("opacity-0","scale-90");

        // Cards stagger animation
        document.querySelectorAll(".ctaItem").forEach((el, i) => {
          setTimeout(() => {
            el.classList.remove("opacity-0","scale-90");
          }, i * 300);
        });

        ctaObserver.disconnect();
      }
    });
  }, { threshold: 0.3 });

  ctaObserver.observe(document.querySelector("#ctaTitle"));
//2nd
  const trustObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        // Animate fade-in for all items
        document.querySelectorAll("#trustTitle, #trustText, .trustItem").forEach((el, i) => {
          setTimeout(() => {
            el.classList.remove("opacity-0", "translate-y-6");
          }, i * 200); // stagger effect
        });

        // Counter animation
        document.querySelectorAll(".counter").forEach(counter => {
          const target = +counter.getAttribute("data-target");
          let count = 0;
          const step = Math.ceil(target / 100); // adjust speed
          const updateCounter = () => {
            count += step;
            if (count > target) count = target;
            counter.textContent = count.toLocaleString() + (target >= 1000 ? "+" : "%");
            if (count < target) requestAnimationFrame(updateCounter);
          };
          updateCounter();
        });

        trustObserver.disconnect();
      }
    });
  }, { threshold: 0.3 });

  trustObserver.observe(document.querySelector("#trustTitle"));
//3rd

  // Hero Section Animation
  window.addEventListener("DOMContentLoaded", () => {
    const left = document.getElementById("leftContent");
    const right = document.getElementById("rightContent");

    setTimeout(() => {
      left.classList.remove("opacity-0", "-translate-x-10");
      right.classList.remove("opacity-0", "translate-x-10");
    }, 200); // delay for smooth effect
  });
//4th
  // Observer for Why Choose PharmaHub section
  const whyObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        // Title + Text animate
        document.querySelector("#whyTitle").classList.remove("opacity-0", "translate-y-6");
        document.querySelector("#whyText").classList.remove("opacity-0", "translate-y-6");

        // Cards animate ek ek karke (300ms delay each)
        document.querySelectorAll(".cardAnim").forEach((el, i) => {
          setTimeout(() => {
            el.classList.remove("opacity-0", "translate-y-10");
          }, i * 300);
        });

        whyObserver.disconnect(); // ek hi baar chale
      }
    });
  }, { threshold: 0.3 });

  // Observe only section title (jab wo visible hoga tab trigger hoga)
  whyObserver.observe(document.querySelector("#whyTitle"));
//5th
  // Observer for "How PharmaHub Works" section
  const howObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {

        // Animate Title + Text
        document.querySelector("#howTitle").classList.remove("opacity-0", "translate-y-6");
        document.querySelector("#howText").classList.remove("opacity-0", "translate-y-6");

        // Animate Steps one by one with delay
        document.querySelectorAll(".howStep").forEach((step, i) => {
          setTimeout(() => {
            step.classList.remove("opacity-0", "-translate-x-10");
          }, i * 300); // har step 300ms gap se trigger hoga
        });

        howObserver.disconnect(); // ek hi baar chale
      }
    });
  }, { threshold: 0.3 });

  // Observe only the title (jab wo screen pe aaye to trigger)
  howObserver.observe(document.querySelector("#howTitle"));
//6th
//✅ baaki saara code jo tumne diya tha bilkul same hai (Hero, Why, How, Trusted, CTA, Footer, Scripts) 

const footerObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      document.querySelectorAll("#footer, .footerItem").forEach((el, i) => {
        setTimeout(() => {
          el.classList.remove("opacity-0", "translate-y-6");
        }, i * 200); // stagger effect
      });
      footerObserver.disconnect();
    }
  });
}, { threshold: 0.2 });

footerObserver.observe(document.querySelector("#footer"));



// Initialize Swiper 7th section
  var swiper = new Swiper(".mySwiper", {
    slidesPerView: 3,
    spaceBetween: 24,
    loop: true,
    autoplay: {
      delay: 1500,
      disableOnInteraction: false,
    },
    
    breakpoints: {
      640: { slidesPerView: 1 },
      768: { slidesPerView: 2 },
      1024: { slidesPerView: 3 },
    },
  });

//<!-- join  our platform js -->
// Tab functionality 8th
document.addEventListener('DOMContentLoaded', function() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTabName = this.getAttribute('data-tab');
            const targetContentId = targetTabName + '-tab';

            // Buttons ki styling
            tabButtons.forEach(btn => {
                btn.classList.remove('text-primary', 'border-b-2', 'border-primary', 'bg-blue-50');
                btn.classList.add('text-gray-500');
            });

            this.classList.remove('text-gray-500');
            this.classList.add('text-primary', 'border-b-2', 'border-primary', 'bg-blue-50');

            // Content ko switch karna
            tabContents.forEach(content => {
                content.classList.add('hidden');
            });

            const activeContent = document.getElementById(targetContentId);
            if (activeContent) {
                activeContent.classList.remove('hidden');
            }
        });
    });
});
// Apply for pharmacy js 9th
// 1. Function to open the modal
function openModal(modalId) {
    const modal = document.getElementById(modalId);
        const modalContent = document.getElementById('pharmacy-modal-content');

        if (modal) {
            // Ensure form and success message are in the correct state
            document.getElementById('pharmacy-apply-form').classList.remove('hidden');
            document.getElementById('success-message').classList.add('hidden');

            modal.classList.remove('hidden');
            // Transition effect
            void modalContent.offsetWidth; 
            modalContent.classList.remove('opacity-0', 'scale-95');
            modalContent.classList.add('opacity-100', 'scale-100');
        }
    }

    // 2. Function to close the modal
    function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        const modalContent = document.getElementById('pharmacy-modal-content');
        
        if (modal) {
            // Transition effect
            modalContent.classList.remove('opacity-100', 'scale-100');
            modalContent.classList.add('opacity-0', 'scale-95');

            // Wait for transition to finish before hiding
            setTimeout(() => {
                modal.classList.add('hidden');
                // Reset form on close
                document.getElementById('pharmacy-apply-form').reset();
            }, 300); 
        }
    }

    // 3. Form Submission Handling (AJAX)
    document.addEventListener('DOMContentLoaded', () => {
        const form = document.getElementById('pharmacy-apply-form');
        
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault(); // Default form submission rokna
                
                // Form data
                const formData = new FormData(form);
                const actionUrl = form.getAttribute('action');
                
                // Demo Success Logic (Replace this with real AJAX/Fetch in Django)
                console.log('Attempting to submit form to:', actionUrl);
                
                // Example of how you would send the data asynchronously:
                /*
                fetch(actionUrl, {
                    method: 'POST',
                    body: formData,
                    // Django CSRF token yahan add karna hoga
                })
                .then(response => {
                    if (response.ok) return response.json();
                    throw new Error('Network response was not ok.');
                })
                .then(data => {
                    // Success: Form hide karo aur success message dikhao
                    form.classList.add('hidden');
                    document.getElementById('success-message').classList.remove('hidden');
                })
                .catch(error => {
                    console.error('Submission error:', error);
                    alert('An error occurred during submission.');
                });
                */
                
                // For now, only show the success message instantly (like a demo):
                form.classList.add('hidden');
                document.getElementById('success-message').classList.remove('hidden');
            });
        }
    });
