class CustomNavbar extends HTMLElement {
    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `
            <style>
                .navbar {
                    background-color: #2E7D32;
                    height: 4rem;
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    z-index: 10;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                
                .navbar-container {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    height: 100%;
                    padding: 0 2rem;
                    max-width: 100%;
                }
                
                .logo-container {
                    display: flex;
                    align-items: center;
                    color: white;
                }
                
                .logo-text {
                    font-size: 1.25rem;
                    font-weight: 600;
                    margin-left: 0.75rem;
                }
                
                .user-menu {
                    display: flex;
                    align-items: center;
                    color: white;
                }
                
                .user-avatar {
                    width: 2.5rem;
                    height: 2.5rem;
                    border-radius: 50%;
                    background-color: #81C784;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-left: 1rem;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }
                
                .user-avatar:hover {
                    background-color: #66BB6A;
                }
                
                .notification-icon {
                    position: relative;
                    cursor: pointer;
                    margin-right: 1.5rem;
                }
                
                .notification-badge {
                    position: absolute;
                    top: -5px;
                    right: -5px;
                    background-color: #FF5252;
                    color: white;
                    border-radius: 50%;
                    width: 18px;
                    height: 18px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 0.6rem;
                    font-weight: 600;
                }
            </style>
            
            <nav class="navbar">
                <div class="navbar-container">
                    <div class="logo-container">
                        <i data-feather="activity"></i>
                        <span class="logo-text">PharmaProfit Pro</span>
                    </div>
                    
                    <div class="user-menu">
                        <div class="notification-icon">
                            <i data-feather="bell"></i>
                            <span class="notification-badge">3</span>
                        </div>
                        <div class="user-avatar">
                            <i data-feather="user"></i>
                        </div>
                    </div>
                </div>
            </nav>
        `;
    }
}

customElements.define('custom-navbar', CustomNavbar);