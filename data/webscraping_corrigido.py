
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin, urlparse

def scrape_table_all_pages(base_url, table_class="tbl-container bdr"):
    """
    Extrai dados de uma tabela com paginação

    Args:
        base_url: URL da primeira página
        table_class: Classe CSS da tabela

    Returns:
        DataFrame com todos os dados extraídos
    """

    all_data = []
    current_page = 1

    # Headers para simular um navegador real
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    session = requests.Session()
    session.headers.update(headers)

    while True:
        print(f"Processando página {current_page}...")

        try:
            # Faz a requisição
            response = session.get(base_url)
            response.raise_for_status()

            # Parse do HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Encontra a tabela
            table = soup.find('table', class_=table_class)
            if not table:
                # Tenta encontrar por classe parcial
                table = soup.find('table', class_=lambda x: x and 'tbl-container' in x)

            if not table:
                print("Tabela não encontrada na página")
                break

            # Extrai dados da tabela
            page_data = extract_table_data(table)

            if not page_data:
                print("Nenhum dado encontrado na tabela")
                break

            all_data.extend(page_data)
            print(f"Extraídos {len(page_data)} registros da página {current_page}")

            # AQUI ESTÁ A MUDANÇA: Procura pelo botão com a classe específica
            next_url = find_next_page_url_specific(soup, base_url)

            if not next_url:
                print("Não há mais páginas para processar")
                break

            base_url = next_url
            current_page += 1

            # Pausa entre requisições para não sobrecarregar o servidor
            time.sleep(1)

        except requests.RequestException as e:
            print(f"Erro na requisição: {e}")
            break
        except Exception as e:
            print(f"Erro inesperado: {e}")
            break

    return pd.DataFrame(all_data)

def extract_table_data(table):
    """
    Extrai dados de uma tabela HTML
    """
    data = []

    # Encontra o cabeçalho
    headers = []
    header_row = table.find('thead')
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
    else:
        # Se não há thead, usa a primeira linha como cabeçalho
        first_row = table.find('tr')
        if first_row:
            headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]

    # Extrai dados do corpo da tabela
    tbody = table.find('tbody')
    rows = tbody.find_all('tr') if tbody else table.find_all('tr')[1:]  # Pula cabeçalho se não há tbody

    for row in rows:
        cells = row.find_all(['td', 'th'])
        if cells:
            row_data = {}
            for i, cell in enumerate(cells):
                header = headers[i] if i < len(headers) else f'Coluna_{i+1}'
                row_data[header] = cell.get_text(strip=True)
            data.append(row_data)

    return data

def find_next_page_url_specific(soup, current_url):
    """
    Encontra a URL da próxima página usando a classe específica
    """
    # Procura pelo botão com a classe específica que você forneceu
    next_button = soup.find('a', class_='btn-navigation btn-navigation-next')

    if next_button and next_button.get('href'):
        next_url = urljoin(current_url, next_button['href'])
        print(f"Próxima página encontrada: {next_url}")
        return next_url

    # Alternativa: procura por qualquer elemento com essas classes
    next_button = soup.find(attrs={'class': lambda x: x and 'btn-navigation-next' in x})

    if next_button and next_button.get('href'):
        next_url = urljoin(current_url, next_button['href'])
        print(f"Próxima página encontrada (alternativa): {next_url}")
        return next_url

    # Se não encontrou, verifica se o botão existe mas está desabilitado
    disabled_button = soup.find('a', class_=lambda x: x and 'btn-navigation-next' in x and 'disabled' in x)
    if disabled_button:
        print("Botão 'Próxima' encontrado mas está desabilitado (última página)")
    else:
        print("Botão 'Próxima' não encontrado na página")

    return None

# VERSÃO COM SELENIUM (mais robusta para sites com JavaScript)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def scrape_with_selenium_specific(url, table_class="tbl-container bdr"):
    """
    Web scraping usando Selenium com a classe específica do botão
    """
    # Configurações do Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Remove esta linha para ver o navegador
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
            try:
                table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "tbl-container")))
            except:
                print("Tabela não encontrada")
                break

            # Extrai dados da página atual
            page_data = extract_selenium_table_data(driver, table_class)

            if not page_data:
                print("Nenhum dado encontrado na tabela")
                break

            all_data.extend(page_data)
            print(f"Extraídos {len(page_data)} registros da página {page}")

            # AQUI ESTÁ A MUDANÇA: Procura pelo botão com a classe específica
            try:
                # Primeiro tenta encontrar o botão
                next_button = driver.find_element(By.CLASS_NAME, "btn-navigation-next")

                # Verifica se o botão está habilitado
                if next_button.is_enabled() and "disabled" not in next_button.get_attribute("class"):
                    print("Clicando no botão 'Próxima'...")
                    driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(3)  # Aguarda carregar a próxima página
                    page += 1
                else:
                    print("Botão 'Próxima' está desabilitado (última página)")
                    break

            except Exception as e:
                print(f"Botão 'Próxima' não encontrado ou erro: {e}")
                break

    finally:
        driver.quit()

    return pd.DataFrame(all_data)

def extract_selenium_table_data(driver, table_class):
    """
    Extrai dados usando Selenium
    """
    data = []

    try:
        # Procura a tabela pela classe
        table = driver.find_element(By.CSS_SELECTOR, f"table.{table_class.replace(' ', '.')}")
        rows = table.find_elements(By.TAG_NAME, "tr")

        # Pega cabeçalhos
        headers = []
        if rows:
            header_cells = rows[0].find_elements(By.TAG_NAME, "th")
            if not header_cells:
                header_cells = rows[0].find_elements(By.TAG_NAME, "td")
            headers = [cell.text.strip() for cell in header_cells]

        # Extrai dados
        for row in rows[1:]:  # Pula cabeçalho
            cells = row.find_elements(By.TAG_NAME, "td")
            if cells:
                row_data = {}
                for i, cell in enumerate(cells):
                    header = headers[i] if i < len(headers) else f'Coluna_{i+1}'
                    row_data[header] = cell.text.strip()
                data.append(row_data)

    except Exception as e:
        print(f"Erro ao extrair dados: {e}")

    return data

# EXEMPLO DE USO
if __name__ == "__main__":
    # COLOQUE SUA URL AQUI
    url = "https://seusite.com/pagina-com-tabela"  # ← MUDE AQUI

    print("Escolha o método:")
    print("1 - Requests + BeautifulSoup (mais rápido)")
    print("2 - Selenium (mais robusto para JavaScript)")

    metodo = input("Digite 1 ou 2: ").strip()

    if metodo == "1":
        print("\nUsando Requests + BeautifulSoup...")
        df = scrape_table_all_pages(url)
    else:
        print("\nUsando Selenium...")
        df = scrape_with_selenium_specific(url)

    if not df.empty:
        print(f"\nTotal de registros extraídos: {len(df)}")
        print("\nPrimeiras 5 linhas:")
        print(df.head())

        # Salva em CSV
        filename = 'dados_extraidos.csv'
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"\nDados salvos em '{filename}'")
    else:
        print("Nenhum dado foi extraído")
