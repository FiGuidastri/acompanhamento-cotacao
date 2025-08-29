from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time
import re
import requests
from PIL import Image
import pytesseract
from io import BytesIO

def scrape_with_selenium_image_prices(url, table_class="table table-main"):
    """
    Web scraping com OCR para preços em imagem
    """
    # Configurações do Chrome
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=chrome_options)
    all_data = []
    
    try:
        driver.get(url)
        print("Página carregada, aguardando tabela...")
        
        wait = WebDriverWait(driver, 15)
        table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.table-main")))
        time.sleep(5)  # Aguarda carregar completamente
        
        # Extrai dados da primeira página
        page_data = extract_with_image_ocr(driver, table_class)
        
        if page_data:
            all_data.extend(page_data)
            print(f"Extraídos {len(page_data)} registros")
                
    finally:
        driver.quit()
    
    return pd.DataFrame(all_data)

def extract_with_image_ocr(driver, table_class):
    """
    Extrai dados incluindo preços de imagens usando OCR
    """
    data = []
    
    try:
        table = driver.find_element(By.CSS_SELECTOR, f"table.{table_class.replace(' ', '.')}")
        rows = table.find_elements(By.TAG_NAME, "tr")
        
        print(f"Encontradas {len(rows)} linhas na tabela")
        
        # Pega cabeçalhos
        headers = []
        if rows:
            header_cells = rows[0].find_elements(By.TAG_NAME, "th")
            headers = [cell.text.strip() for cell in header_cells if cell.text.strip()]
            print(f"Cabeçalhos: {headers}")
        
        # Processa as primeiras 20 linhas
        for i, row in enumerate(rows[1:21], 1):
            cells = row.find_elements(By.TAG_NAME, "td")
            
            if len(cells) >= 3:
                row_data = {}
                
                for j, cell in enumerate(cells):
                    header = headers[j] if j < len(headers) else f'Coluna_{j+1}'
                    
                    # Primeiro tenta texto normal
                    text = cell.text.strip()
                    
                    # Se não tem texto e é a coluna de preço, procura imagem
                    if not text and j == 2:  # Coluna de preço (índice 2)
                        # Procura por div com background-image
                        divs = cell.find_elements(By.CSS_SELECTOR, "div[style*='background-image']")
                        
                        for div in divs:
                            style = div.get_attribute('style')
                            print(f"Linha {i}: Style encontrado: {style}")
                            
                            # Extrai URL da imagem
                            url_match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
                            if url_match:
                                img_url = url_match.group(1)
                                print(f"URL da imagem: {img_url}")
                                
                                # Se é URL relativa, completa
                                if img_url.startswith('/'):
                                    img_url = 'https://www.agrolink.com.br' + img_url
                                
                                # Tenta fazer OCR na imagem
                                try:
                                    price_text = ocr_price_from_url(img_url)
                                    if price_text:
                                        text = price_text
                                        print(f"Preço extraído via OCR: {price_text}")
                                except Exception as e:
                                    print(f"Erro no OCR: {e}")
                    
                    row_data[header] = text
                
                if any(value.strip() for value in row_data.values() if value):
                    data.append(row_data)
                    print(f"Linha {i} processada: {row_data}")
                
    except Exception as e:
        print(f"Erro ao extrair dados: {e}")
        import traceback
        traceback.print_exc()
    
    return data

def ocr_price_from_url(img_url):
    """
    Faz OCR em uma imagem de preço
    """
    try:
        # Baixa a imagem
        response = requests.get(img_url, timeout=10)
        response.raise_for_status()
        
        # Abre a imagem
        image = Image.open(BytesIO(response.content))
        
        # Faz OCR
        text = pytesseract.image_to_string(image, config='--psm 8 -c tessedit_char_whitelist=0123456789,.')
        
        # Limpa o texto
        text = re.sub(r'[^\d,.]', '', text.strip())
        
        return text if text else None
        
    except Exception as e:
        print(f"Erro no OCR da URL {img_url}: {e}")
        return None

# Versão alternativa sem OCR - apenas extrai as URLs das imagens
def scrape_image_urls_only(url, table_class="table table-main"):
    """
    Versão que apenas extrai as URLs das imagens de preço
    """
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=chrome_options)
    all_data = []
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.table-main")))
        time.sleep(5)
        
        table = driver.find_element(By.CSS_SELECTOR, f"table.{table_class.replace(' ', '.')}")
        rows = table.find_elements(By.TAG_NAME, "tr")
        
        # Cabeçalhos
        headers = []
        if rows:
            header_cells = rows[0].find_elements(By.TAG_NAME, "th")
            headers = [cell.text.strip() for cell in header_cells if cell.text.strip()]
        
        for i, row in enumerate(rows[1:21], 1):
            cells = row.find_elements(By.TAG_NAME, "td")
            
            if len(cells) >= 3:
                row_data = {}
                
                for j, cell in enumerate(cells):
                    header = headers[j] if j < len(headers) else f'Coluna_{j+1}'
                    text = cell.text.strip()
                    
                    # Para coluna de preço, também salva URL da imagem
                    if j == 2:  # Coluna de preço
                        divs = cell.find_elements(By.CSS_SELECTOR, "div[style*='background-image']")
                        if divs:
                            style = divs[0].get_attribute('style')
                            url_match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
                            if url_match:
                                img_url = url_match.group(1)
                                if img_url.startswith('/'):
                                    img_url = 'https://www.agrolink.com.br' + img_url
                                text = f"IMAGEM: {img_url}"
                    
                    row_data[header] = text
                
                if any(value.strip() for value in row_data.values() if value):
                    all_data.append(row_data)
                
    finally:
        driver.quit()
    
    return pd.DataFrame(all_data)

# Para usar
if __name__ == "__main__":
    url = "https://www.agrolink.com.br/cotacoes/graos/soja/"
    
    print("Extraindo URLs das imagens de preço...")
    df = scrape_image_urls_only(url)
    
    if not df.empty:
        print(f"Total extraído: {len(df)} registros")
        print(df.head(10))
        
        df.to_csv('dados_com_urls_imagens.csv', index=False, encoding='utf-8')
        print("Dados salvos em 'dados_com_urls_imagens.csv'!")
    else:
        print("Nenhum dado foi extraído")