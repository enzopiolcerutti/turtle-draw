from collections import deque
from pathlib import Path

import cv2
import numpy as np


def carregar_imagem(caminho_imagem):
    # Eu uso OpenCV somente aqui, porque o enunciado permite usar a biblioteca para leitura.
    imagem_bgr = cv2.imread(str(caminho_imagem), cv2.IMREAD_COLOR)
    if imagem_bgr is None:
        raise FileNotFoundError(f"Imagem nao encontrada: {caminho_imagem}")

    imagem_rgb = imagem_bgr[..., ::-1]
    return imagem_rgb.astype(np.float32) / 255.0


def converter_para_cinza(imagem_rgb):
    # Eu uso pesos perceptuais para preservar melhor a luminosidade percebida da imagem.
    pesos = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return imagem_rgb @ pesos


def recortar_regiao_do_cachorro(imagem_cinza):
    # Eu recorto a regiao onde o cachorro aparece para evitar que o fundo vazio vire ruido.
    y_inicial, y_final = 50, 720
    x_inicial, x_final = 180, 690
    return imagem_cinza[y_inicial:y_final, x_inicial:x_final]


def redimensionar_bilinear(imagem, nova_altura, nova_largura):
    # Eu reduzo a imagem manualmente para gerar menos pontos para o turtlesim seguir.
    altura, largura = imagem.shape
    posicoes_y = np.linspace(0, altura - 1, nova_altura)
    posicoes_x = np.linspace(0, largura - 1, nova_largura)
    grade_x, grade_y = np.meshgrid(posicoes_x, posicoes_y)

    x0 = np.floor(grade_x).astype(int)
    y0 = np.floor(grade_y).astype(int)
    x1 = np.clip(x0 + 1, 0, largura - 1)
    y1 = np.clip(y0 + 1, 0, altura - 1)

    peso_x = grade_x - x0
    peso_y = grade_y - y0

    topo = (1 - peso_x) * imagem[y0, x0] + peso_x * imagem[y0, x1] 
    base = (1 - peso_x) * imagem[y1, x0] + peso_x * imagem[y1, x1]
    return ((1 - peso_y) * topo + peso_y * base).astype(np.float32)


def criar_kernel_gaussiano(tamanho=7, sigma=1.6):
    # Eu deixei o filtro um pouco mais forte para suavizar pelo e sombra antes da borda.
    raio = tamanho // 2
    eixo = np.arange(-raio, raio + 1)
    grade_x, grade_y = np.meshgrid(eixo, eixo)
    kernel = np.exp(-(grade_x**2 + grade_y**2) / (2 * sigma**2))
    return (kernel / kernel.sum()).astype(np.float32)


def convoluir_2d(imagem, kernel):
    # Esta convolucao e manual para nao depender de filtros prontos de bibliotecas externas.
    altura_kernel, largura_kernel = kernel.shape
    borda_y = altura_kernel // 2
    borda_x = largura_kernel // 2
    imagem_com_borda = np.pad(
        imagem,
        ((borda_y, borda_y), (borda_x, borda_x)),
        mode="edge",
    )
    saida = np.zeros_like(imagem, dtype=np.float32)

    for y in range(imagem.shape[0]):
        for x in range(imagem.shape[1]):
            regiao = imagem_com_borda[y:y + altura_kernel, x:x + largura_kernel]
            saida[y, x] = np.sum(regiao * kernel)

    return saida


def normalizar_por_percentis(imagem, percentil_baixo=2, percentil_alto=98):
    # Eu normalizo por percentis para evitar que pontos muito claros/escuros dominem o contraste.
    valor_baixo, valor_alto = np.percentile(imagem, [percentil_baixo, percentil_alto])
    normalizada = (imagem - valor_baixo) / (valor_alto - valor_baixo + 1e-8)
    return np.clip(normalizada, 0, 1).astype(np.float32)


def dilatar(mascara):
    resultado = np.zeros_like(mascara, dtype=bool)
    mascara_com_borda = np.pad(mascara, 1, mode="constant", constant_values=False)

    for deslocamento_y in range(3):
        for deslocamento_x in range(3):
            resultado |= mascara_com_borda[
                deslocamento_y:deslocamento_y + mascara.shape[0],
                deslocamento_x:deslocamento_x + mascara.shape[1],
            ]

    return resultado


def erodir(mascara):
    resultado = np.ones_like(mascara, dtype=bool)
    mascara_com_borda = np.pad(mascara, 1, mode="constant", constant_values=False)

    for deslocamento_y in range(3):
        for deslocamento_x in range(3):
            resultado &= mascara_com_borda[
                deslocamento_y:deslocamento_y + mascara.shape[0],
                deslocamento_x:deslocamento_x + mascara.shape[1],
            ]

    return resultado


def fechar_mascara(mascara, repeticoes=2):
    # Fechamento: eu uno pequenas quebras para a silhueta lateral ficar mais continua.
    resultado = mascara.copy()
    for _ in range(repeticoes):
        resultado = erodir(dilatar(resultado))
    return resultado


def abrir_mascara(mascara, repeticoes=1):
    # Abertura: eu removo pequenos pontos isolados que apareceriam como sujeira no desenho.
    resultado = mascara.copy()
    for _ in range(repeticoes):
        resultado = dilatar(erodir(resultado))
    return resultado


def preencher_buracos(mascara):
    # Eu preencho buracos internos para transformar textura do pelo em uma silhueta mais limpa.
    altura, largura = mascara.shape
    fundo_visitado = np.zeros_like(mascara, dtype=bool)
    fila = deque()

    for x in range(largura):
        fila.append((0, x))
        fila.append((altura - 1, x))
    for y in range(altura):
        fila.append((y, 0))
        fila.append((y, largura - 1))

    while fila:
        y, x = fila.popleft()
        if y < 0 or y >= altura or x < 0 or x >= largura:
            continue
        if fundo_visitado[y, x] or mascara[y, x]:
            continue

        fundo_visitado[y, x] = True
        fila.extend([(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)])

    return mascara | ~fundo_visitado


def remover_sombra_inferior_esquerda(mascara):
    # Nesta imagem a sombra do chao entrava na mascara; eu corto essa regiao manualmente.
    limpa = mascara.copy()
    altura, largura = limpa.shape
    inicio_y = int(altura * 0.84)
    limite_x = int(largura * 0.17)

    limpa[inicio_y:, :limite_x] = False
    limpa[-3:, :] = False
    return limpa


def buscar_maior_componente(mascara):
    # Eu mantenho apenas a maior componente conectada, assumindo que ela e o cachorro.
    altura, largura = mascara.shape
    visitado = np.zeros_like(mascara, dtype=bool)
    melhor_componente = []
    vizinhos = [(-1, 0), (0, -1), (0, 1), (1, 0)]

    for y in range(altura):
        for x in range(largura):
            if visitado[y, x] or not mascara[y, x]:
                continue

            fila = deque([(y, x)])
            visitado[y, x] = True
            componente = []

            while fila:
                atual_y, atual_x = fila.popleft()
                componente.append((atual_y, atual_x))

                for deslocamento_y, deslocamento_x in vizinhos:
                    vizinho_y = atual_y + deslocamento_y
                    vizinho_x = atual_x + deslocamento_x

                    dentro_y = 0 <= vizinho_y < altura
                    dentro_x = 0 <= vizinho_x < largura
                    if not (dentro_y and dentro_x):
                        continue

                    if visitado[vizinho_y, vizinho_x] or not mascara[vizinho_y, vizinho_x]:
                        continue

                    visitado[vizinho_y, vizinho_x] = True
                    fila.append((vizinho_y, vizinho_x))

            if len(componente) > len(melhor_componente):
                melhor_componente = componente

    maior = np.zeros_like(mascara, dtype=bool)
    for y, x in melhor_componente:
        maior[y, x] = True

    return maior


def criar_mascara_do_cachorro(imagem_tratada):
    # Aqui eu transformo a imagem tratada em uma mascara binaria limpa do cachorro.
    limiar = np.percentile(imagem_tratada, 43)
    mascara = imagem_tratada < limiar
    mascara = fechar_mascara(mascara, repeticoes=4)
    mascara = abrir_mascara(mascara)
    mascara = buscar_maior_componente(mascara)
    mascara = remover_sombra_inferior_esquerda(mascara)
    mascara = fechar_mascara(mascara, repeticoes=2)
    mascara = preencher_buracos(mascara)
    return buscar_maior_componente(mascara)


def extrair_borda_da_mascara(mascara):
    # A borda externa e a diferenca entre a mascara cheia e a mascara erodida.
    return mascara & ~erodir(mascara)


def ordenar_por_vizinho_mais_proximo(pontos, salto=4, limite_pontos=900):
    # Eu ordeno os pixels por proximidade para transformar a borda em um caminho desenhavel.
    pontos_reduzidos = pontos[::salto].astype(np.float32)
    if len(pontos_reduzidos) == 0:
        return pontos_reduzidos

    indice_inicio = int(np.argmin(pontos_reduzidos[:, 0] + pontos_reduzidos[:, 1]))
    caminho = [pontos_reduzidos[indice_inicio]]
    disponivel = np.ones(len(pontos_reduzidos), dtype=bool)
    disponivel[indice_inicio] = False
    ponto_atual = pontos_reduzidos[indice_inicio]

    while disponivel.any() and len(caminho) < limite_pontos:
        candidatos = pontos_reduzidos[disponivel]
        distancias = np.sum((candidatos - ponto_atual) ** 2, axis=1)
        posicao_proximo = int(np.argmin(distancias))
        indices_disponiveis = np.flatnonzero(disponivel)
        indice_proximo = indices_disponiveis[posicao_proximo]

        ponto_atual = pontos_reduzidos[indice_proximo]
        disponivel[indice_proximo] = False
        caminho.append(ponto_atual)

    return np.array(caminho, dtype=np.float32)


def mapear_para_turtlesim(pontos_pixels, largura_imagem, altura_imagem, margem=1.0):
    # Eu converto coordenadas de pixel para o espaco 0..11 usado pelo turtlesim.
    pontos = pontos_pixels.astype(np.float32)
    coordenadas_x = pontos[:, 1]
    coordenadas_y = pontos[:, 0]

    largura_util = 11.0 - 2 * margem
    altura_util = 11.0 - 2 * margem
    escala = min(largura_util / largura_imagem, altura_util / altura_imagem)

    largura_desenho = largura_imagem * escala
    altura_desenho = altura_imagem * escala
    deslocamento_x = (11.0 - largura_desenho) / 2.0
    deslocamento_y = (11.0 - altura_desenho) / 2.0

    x_turtle = deslocamento_x + coordenadas_x * escala
    y_turtle = 11.0 - (deslocamento_y + coordenadas_y * escala)
    return np.column_stack([x_turtle, y_turtle]).astype(np.float32)


def preparar_imagem_para_desenho(caminho_imagem, largura_processada=280, altura_processada=360):
    # Esta funcao deixa a imagem pronta para a etapa de segmentacao e borda.
    imagem_rgb = carregar_imagem(caminho_imagem)
    imagem_cinza = converter_para_cinza(imagem_rgb)
    recorte = recortar_regiao_do_cachorro(imagem_cinza)
    imagem_reduzida = redimensionar_bilinear(
        recorte,
        altura_processada,
        largura_processada,
    )
    imagem_suavizada = convoluir_2d(imagem_reduzida, criar_kernel_gaussiano())
    return normalizar_por_percentis(imagem_suavizada)


def gerar_caminho_do_cachorro(caminho_imagem):
    # Esta e a funcao principal da visao: ela devolve o caminho que a tartaruga vai seguir.
    largura_processada = 280
    altura_processada = 360
    imagem_tratada = preparar_imagem_para_desenho(
        caminho_imagem,
        largura_processada,
        altura_processada,
    )

    mascara = criar_mascara_do_cachorro(imagem_tratada)
    borda = extrair_borda_da_mascara(mascara)
    pontos_borda = np.argwhere(borda)
    caminho_pixels = ordenar_por_vizinho_mais_proximo(pontos_borda)

    return mapear_para_turtlesim(
        caminho_pixels,
        largura_processada,
        altura_processada,
    )


def main():
    caminho = gerar_caminho_do_cachorro(Path("dog_img/dog.jpg"))
    print(f"Foram gerados {len(caminho)} pontos.")
    print("Primeiros pontos:")
    for x, y in caminho[:10]:
        print(f"x={x:.2f}, y={y:.2f}")


if __name__ == "__main__":
    main()
