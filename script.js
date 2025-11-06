// Global variables
const app = {
    currentUser: {
        name: "Administrador",
        role: "admin",
        avatar: "A"
    },
    settings: {
        defaultMargin: 15,
        currency: "$"
    }
};

// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Sample data table initialization (would be replaced with real data fetch)
    initSampleData();
    
    // Event listeners
    setupEventListeners();
});

function initSampleData() {
    // This would be replaced with actual data fetching logic
    console.log("Initializing sample data...");
}

function setupEventListeners() {
    // Add event listeners for interactive elements
    document.addEventListener('click', function(e) {
        // Handle dropdown menus
        if (e.target.closest('.dropdown-toggle')) {
            const dropdown = e.target.closest('.dropdown-toggle').nextElementSibling;
            dropdown.classList.toggle('hidden');
        }
        
        // Close dropdowns when clicking outside
        if (!e.target.closest('.dropdown')) {
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                menu.classList.add('hidden');
            });
        }
    });
    
    // Handle file upload preview (would be connected to actual Excel processing)
    const fileInputs = document.querySelectorAll('.file-input');
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            if (this.files && this.files[0]) {
                const fileName = this.files[0].name;
                alert(`Archivo seleccionado: ${fileName}\n(En una implementación real, se procesaría el Excel)`);
            }
        });
    });
}

// Utility functions
function formatCurrency(amount) {
    return `${app.settings.currency}${amount.toFixed(2)}`;
}

function calculateFinalPrice(basePrice, marginPercent) {
    return basePrice * (1 + (marginPercent / 100));
}