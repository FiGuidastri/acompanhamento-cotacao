from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time

def scrape_with_selenium(url, table_class="table table-main"):
    """
    Web scraping usando Selenium para sites com JavaScript
    """
    # Configurações do Chrome
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Removido para debug
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=chrome_options)
    all_data = []
    
    try:
        driver.get(url)
        page = 1
        
        while True:
            print(f"Processando página {page}...")
            
            # Aguarda a tabela carregar
            wait = WebDriverWait(driver, 10)
            table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.table-main")))
            
            # Extrai dados da página atual
            page_data = extract_selenium_table_data_fixed(driver, table_class)
            
            if not page_data:
                break
                
            all_data.extend(page_data)
            print(f"Extraídos {len(page_data)} registros da página {page}")
            
            # Procura botão "Próxima página"
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, "a.btn-navigation.btn-navigation-next")
                
                if next_button.is_enabled() and "disabled" not in next_button.get_attribute("class"):
                    driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(3)  # Aguarda carregar
                    page += 1
                else:
                    print("Botão 'Próxima' está desabilitado (última página)")
                    break
            except:
                print("Botão 'Próxima' não encontrado")
                break
                
    finally:
        driver.quit()
    
    return pd.DataFrame(all_data)

def extract_selenium_table_data_fixed(driver, table_class):
    """
    Extrai dados usando Selenium - VERSÃO CORRIGIDA PARA ESTRUTURA ESPECÍFICA
    """
    data = []
    
    try:
        table = driver.find_element(By.CSS_SELECTOR, f"table.{table_class.replace(' ', '.')}")
        rows = table.find_elements(By.TAG_NAME, "tr")
        
        print(f"Encontradas {len(rows)} linhas na tabela")
        
        # Pega cabeçalhos da primeira linha
        headers = []
        if rows:
            header_cells = rows[0].find_elements(By.TAG_NAME, "th")
            if not header_cells:
                header_cells = rows[0].find_elements(By.TAG_NAME, "td")
            headers = [cell.text.strip() for cell in header_cells if cell.text.strip()]
            print(f"Cabeçalhos encontrados: {headers}")
        
        # Extrai dados de todas as linhas
        for i, row in enumerate(rows[1:], 1):  # Pula cabeçalho
            cells = row.find_elements(By.TAG_NAME, "td")
            
            if cells:
                row_data = {}
                
                for j, cell in enumerate(cells):
                    header = headers[j] if j < len(headers) else f'Coluna_{j+1}'
                    
                    # Estratégia específica baseada no HTML que você mostrou
                    text = ""
                    
                    # 1. Primeiro verifica se tem div com classe text-right float-right
                    price_div = cell.find_elements(By.CSS_SELECTOR, "div.text-right.float-right")
                    if price_div:
                        text = price_div[0].text.strip()
                        print(f"Preço encontrado na célula {j}: {text}")
                    
                    # 2. Se não encontrou, pega o texto normal da célula
                    if not text:
                        text = cell.text.strip()
                    
                    # 3. Se ainda não tem texto, tenta innerHTML
                    if not text:
                        inner_html = cell.get_attribute('innerHTML')
                        if 'text-right float-right' in inner_html:
                            # Extrai o texto do div usando JavaScript
                            try:
                                text = driver.execute_script("""
                                    var div = arguments[0].querySelector('div.text-right.float-right');
                                    return div ? div.textContent.trim() : '';
                                """, cell)
                                if text:
                                    print(f"Preço extraído via JavaScript: {text}")
                            except:
                                pass
                    
                    # 4. Se ainda não tem texto, usa textContent
                    if not text:
                        text = cell.get_attribute('textContent').strip()
                    
                    row_data[header] = text if text else ""
                
                # Debug: mostra os dados extraídos
                if any(value.strip() for value in row_data.values() if value):
                    print(f"Linha {i}: {row_data}")
                    data.append(row_data)
                
    except Exception as e:
        print(f"Erro ao extrair dados: {e}")
        import traceback
        traceback.print_exc()
    
    return data

# Para usar o Selenium
if __name__ == "__main__":
    url = "https://www.agrolink.com.br/cotacoes/graos/soja/"
    
    df = scrape_with_selenium(url)
    
    if not df.empty:
        print(f"\nTotal extraído: {len(df)} registros")
        print("\nPrimeiras 5 linhas:")
        print(df.head())
        
        # Verifica se tem preços
        price_col = 'PREÇO (R$)' if 'PREÇO (R$)' in df.columns else df.columns[2]
        df_with_prices = df[df[price_col].notna() & (df[price_col] != '') & (df[price_col] != 'nan')]
        print(f"\nLinhas com preços válidos: {len(df_with_prices)}")
        if len(df_with_prices) > 0:
            print("Exemplos de preços encontrados:")
            print(df_with_prices[[df.columns[0], df.columns[1], price_col]].head())
        
        df.to_csv('dados_selenium_final.csv', index=False, encoding='utf-8')
        print("Dados salvos em 'dados_selenium_final.csv'!")
    else:
        print("Nenhum dado foi extraído")