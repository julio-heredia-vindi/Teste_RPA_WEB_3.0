from flask import Flask, render_template, request, redirect, send_file, flash, url_for
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO
import os
import time
import tempfile
import zipfile
import uuid
import chromedriver_autoinstaller

app = Flask(__name__)
app.secret_key = 'segredo'

CHROMEDRIVER_PATH = chromedriver_autoinstaller.install()

# Mapeia os IDs temporários para caminhos reais
pasta_temp_map = {}

def extrair_tabela_por_data(data_str, pasta_destino):
    driver = None
    try:
        data_formatada = datetime.strptime(data_str, "%Y-%m-%d").strftime("%Y%m%d")
        url = f"https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/derivativos/ajustes-do-pregao/?Data={data_formatada}"

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)
        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "iframe"))
        )
        iframe = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        table = driver.find_element(By.TAG_NAME, "table")
        html = table.get_attribute("outerHTML")
        df = pd.read_html(StringIO(html))[0]

        nome_arquivo = f"{data_formatada}.csv"
        caminho_completo = os.path.join(pasta_destino, nome_arquivo)
        df.to_csv(caminho_completo, index=False, encoding='utf-8-sig')

        return True, nome_arquivo
    except Exception as e:
        return False, str(e)
    finally:
        if driver:
            driver.quit()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data_inicio = request.form["data_inicio"]
        data_fim = request.form["data_fim"]

        if data_fim < data_inicio:
            flash("A data final não pode ser anterior à data inicial.", "error")
            return redirect("/")

        pasta_temp = tempfile.mkdtemp()
        data_atual = datetime.strptime(data_inicio, "%Y-%m-%d")
        data_limite = datetime.strptime(data_fim, "%Y-%m-%d")
        erros = []

        while data_atual <= data_limite:
            data_str = data_atual.strftime("%Y-%m-%d")
            sucesso, msg = extrair_tabela_por_data(data_str, pasta_temp)
            if not sucesso:
                erros.append(f"{data_str}: {msg}")
            data_atual += timedelta(days=1)

        zip_path = os.path.join(pasta_temp, "tabelas_b3.zip")
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for nome_arquivo in os.listdir(pasta_temp):
                if nome_arquivo.endswith(".csv"):
                    zipf.write(os.path.join(pasta_temp, nome_arquivo), arcname=nome_arquivo)

        if erros:
            flash("Alguns arquivos não foram baixados:\n" + "\n".join(erros), "warning")
        else:
            flash("Todos os arquivos foram salvos com sucesso!", "success")

        # Gera um ID único para representar a pasta temporária
        pasta_id = str(uuid.uuid4())
        pasta_temp_map[pasta_id] = pasta_temp

        return render_template("index.html", pasta_id=pasta_id)

    return render_template("index.html")

@app.route("/baixar/<pasta_id>")
def baixar_arquivos(pasta_id):
    pasta_path = pasta_temp_map.get(pasta_id)
    if not pasta_path:
        flash("Caminho de download não encontrado ou expirado.", "error")
        return redirect("/")

    zip_path = os.path.join(pasta_path, "tabelas_b3.zip")
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True)
    else:
        flash("Arquivo ZIP não encontrado.", "error")
        return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



