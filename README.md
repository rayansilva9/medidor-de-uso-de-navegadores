# Medidor de CPU/GPU/RAM por navegador

App desktop para Windows que mede **CPU**, **GPU** e **RAM** apenas dos processos de um navegador escolhido (Chromium, Thorium, Chrome, Brave, Edge ou nome customizado) durante um tempo configurável.

## Requisitos

- Windows 10 ou superior (GPU por processo usa contadores PDH `GPU Engine`)
- Python 3.11+

## Instalação

```powershell
cd (pasta do projeto)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

```powershell
python main.py
```

1. Defina a **duração** (minutos ou segundos).
2. Escolha o **navegador** no menu (ex.: Thorium → mede só `thorium.exe`).
3. Clique em **Iniciar medição** (o navegador precisa estar aberto).
4. Ao terminar, veja **média**, **pico** e **valor atual** de CPU, GPU e RAM.

### Navegadores suportados

| Navegador   | Executável     |
| ----------- | -------------- |
| Utrium Browser | `chrome.exe` com nome do produto "Utrium" |
| Thorium     | `thorium.exe`  |
| Chromium    | `chromium.exe` |
| Chrome      | `chrome.exe` (Google Chrome) |
| Brave       | `brave.exe`    |
| Edge        | `msedge.exe`   |
| Customizado | qualquer `.exe`|

Todos os processos com o mesmo executável são somados (abas, GPU process, utilitários do browser).

## Limitações

- **Somente Windows** — filtro por `.exe` e GPU via PDH são específicos do sistema.
- GPU % é a soma dos engines do processo; em máquinas com várias GPUs pode ultrapassar 100% (comportamento similar ao Gerenciador de Tarefas).
- Extensões ou subprocessos com outro nome de executável não entram na medição.
- Em sistemas sem suporte a contadores `GPU Engine`, a GPU aparece como **N/D**; CPU e RAM continuam funcionando.

## Estrutura

```
main.py
requirements.txt
medidor/
  browsers.py       # presets de navegadores
  process_filter.py # filtro de PIDs por executável
  sampler.py        # loop de amostragem
  aggregator.py     # média, pico, atual
  gpu_pdh.py        # GPU por PID via PDH
  ui.py             # interface gráfica
```
