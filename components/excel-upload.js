class ExcelUpload extends HTMLElement {
    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `
            <style>
                .upload-card {
                    background-color: white;
                    border-radius: 0.5rem;
                    padding: 1.5rem;
                    margin-bottom: 1.5rem;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    border: 1px dashed #81C784;
                }
                
                .upload-header {
                    display: flex;
                    align-items: center;
                    margin-bottom: 1rem;
                }
                
                .upload-title {
                    font-size: 1.125rem;
                    font-weight: 600;
                    color: #2E7D32;
                    margin-left: 0.75rem;
                }
                
                .upload-content {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    padding: 2rem;
                    border: 2px dashed #81C784;
                    border-radius: 0.5rem;
                    background-color: #F9FBF8;
                    margin-bottom: 1rem;
                }
                
                .upload-icon {
                    color: #81C784;
                    margin-bottom: 1rem;
                }
                
                .upload-text {
                    text-align: center;
                    margin-bottom: 1.5rem;
                }
                
                .upload-text h3 {
                    font-weight: 600;
                    color: #333;
                    margin-bottom: 0.5rem;
                }
                
                .upload-text p {
                    color: #666;
                    font-size: 0.875rem;
                }
                
                .upload-btn {
                    background: linear-gradient(135deg, #2E7D32 0%, #81C784 100%);
                    color: white;
                    padding: 0.5rem 1.5rem;
                    border-radius: 0.375rem;
                    display: inline-flex;
                    align-items: center;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }
                
                .upload-btn:hover {
                    background: linear-gradient(135deg, #1B5E20 0%, #66BB6A 100%);
                    transform: translateY(-2px);
                }
                
                .upload-btn i {
                    margin-right: 0.5rem;
                }
                
                .file-input {
                    display: none;
                }
                
                .margin-control {
                    display: flex;
                    align-items: center;
                    margin-top: 1rem;
                }
                
                .margin-input {
                    width: 5rem;
                    padding: 0.5rem;
                    border: 1px solid #ddd;
                    border-radius: 0.375rem;
                    margin-right: 0.5rem;
                    text-align: right;
                }
                
                .apply-btn {
                    background-color: #2E7D32;
                    color: white;
                    padding: 0.5rem 1rem;
                    border-radius: 0.375rem;
                    cursor: pointer;
                    transition: background-color 0.3s ease;
                }
                
                .apply-btn:hover {
                    background-color: #1B5E20;
                }
            </style>
            
            <div class="upload-card">
                <div class="upload-header">
                    <i data-feather="upload-cloud" class="w-6 h-6 text-emerald-500"></i>
                    <h2 class="upload-title">Importar Productos desde Excel</h2>
                </div>
                
                <div class="upload-content">
                    <i data-feather="file" class="upload-icon w-10 h-10"></i>
                    <div class="upload-text">
                        <h3>Arrastra tu archivo Excel aquí o haz clic para seleccionar</h3>
                        <p>Solo archivos .xlsx con columnas: Código, Producto, Descripción, Precio Proveedor</p>
                    </div>
                    <label class="upload-btn">
                        <i data-feather="upload"></i>
                        Seleccionar Archivo
                        <input type="file" class="file-input" accept=".xlsx">
                    </label>
                </div>
                
                <div class="margin-control">
                    <span>Aplicar margen general:</span>
                    <input type="number" value="15" class="margin-input">
                    <span>%</span>
                    <button class="apply-btn ml-2">Aplicar</button>
                </div>
            </div>
        `;
    }
}

customElements.define('custom-excel-upload', ExcelUpload);