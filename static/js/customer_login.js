
  const tabs = document.querySelectorAll('#tabs button');
  const forms = document.querySelectorAll('#forms form');

  // 1. Initial State Set Karein (Rider ko bhi hide karein)
  document.getElementById('pharmacy-form').classList.add('hidden');
  document.getElementById('rider-form').classList.add('hidden'); // ✅ NEW: Rider form hide kiya
  
  document.getElementById('customer-tab').classList.add('border-teal-600');
  document.getElementById('pharmacy-tab').classList.add('border-transparent');
  document.getElementById('rider-tab').classList.add('border-transparent'); // ✅ NEW: Rider tab border set

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetFormId = tab.getAttribute('data-tab');

      // Reset tabs styles
      tabs.forEach(t => {
        // Sabhi color classes reset karein
        t.classList.remove('tab-active', 'border-teal-600', 'border-orange-500', 'border-blue-600'); 
        t.classList.add('tab-inactive', 'border-transparent');
      });

      // Set active tab style
      tab.classList.add('tab-active');
      tab.classList.remove('tab-inactive');
      
      // 2. Color Logic Update Karein (Rider ke liye Blue)
      if(targetFormId === 'customer-form') {
         tab.classList.add('border-teal-600');
      } else if(targetFormId === 'pharmacy-form') {
         tab.classList.add('border-orange-500');
      } else { // Agar Rider Form hai
         tab.classList.add('border-blue-600');
      }

      // Show/Hide forms
      forms.forEach(f => {
        if (f.id === targetFormId) {
          f.classList.remove('hidden');
        } else {
          f.classList.add('hidden');
        }
      });
    });
  });

