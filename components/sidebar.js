class CustomSidebar extends HTMLElement {
    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `
            <style>
                .sidebar {
                    width: 16rem;
                    background-color: white;
                    height: calc(100vh - 4rem);
                    position: fixed;
                    left: 0;
                    top: 4rem;
                    box-shadow: 1px 0 3px rgba(0,0,0,0.1);
                    transition: all 0.3s ease;
                    z-index: 5;
                }
                
                .sidebar-menu {
                    padding: 1.5rem 0;
                }
                
                .menu-item {
                    display: flex;
                    align-items: center;
                    padding: 0.75rem 1.5rem;
                    color: #333;
                    text-decoration: none;
                    transition: all 0.2s ease;
                }
                
                .menu-item:hover {
                    background-color: rgba(46, 125, 50, 0.1);
                    color: #2E7D32;
                }
                
                .menu-item.active {
                    background-color: rgba(46, 125, 50, 0.2);
                    color: #2E7D32;
                    border-left: 3px solid #2E7D32;
                }
                
                .menu-item i {
                    margin-right: 0.75rem;
                    width: 1.25rem;
                    height: 1.25rem;
                }
                
                .menu-title {
                    font-size: 0.85rem;
                    font-weight: 500;
                    text-transform: uppercase;
                    color: #666;
                    padding: 1rem 1.5rem 0.5rem;
                    margin-top: 1rem;
                }
                
                .menu-divider {
                    border-top: 1px solid #eee;
                    margin: 1rem 1.5rem;
                }
            </style>
            
            <aside class="sidebar">
                <div class="sidebar-menu">
                    <div class="menu-title">Principal</div>
                    <a href="#" class="menu-item active">
                        <i data-feather="home"></i>
                        Dashboard
                    </a>
                    
                    <div class="menu-title">Operaciones</div>
                    <a href="#" class="menu-item">
                        <i data-feather="package"></i>
                        Productos
                    </a>
                    <a href="#" class="menu-item">
                        <i data-feather="users"></i>
                        Clientes
                    </a>
                    <a href="#" class="menu-item">
                        <i data-feather="shopping-cart"></i>
                        Ventas
                    </a>
                    
                    <div class="menu-divider"></div>
                    
                    <div class="menu-title">Configuración</div>
                    <a href="#" class="menu-item">
                        <i data-feather="dollar-sign"></i>
                        Margen de Ganancia
                    </a>
                    <a href="#" class="menu-item">
                        <i data-feather="file-text"></i>
                        Plantillas PDF
                    </a>
                    <a href="#" class="menu-item">
                        <i data-feather="settings"></i>
                        Configuración
                    </a>
                </div>
            </aside>
        `;
    }
}

customElements.define('custom-sidebar', CustomSidebar);