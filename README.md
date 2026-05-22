# Turtle Draw

Este projeto foi desenvolvido para a atividade ponderada de visão computacional com ROS 2. A ideia foi pegar uma imagem de um cachorro, tratar essa imagem e transformar o contorno encontrado em comandos para a tartaruga do `turtlesim` preencher.

Eu escolhi deixar o fluxo fácil de entender, então primeiro preparo a imagem, depois extraio uma borda limpa e, por fim, mando a tartaruga seguir os pontos desse contorno.

## Como eu desenvolvi

Comecei explorando a imagem no notebook `tratamento_imagem_cachorro.ipynb`. Nele eu fui testando as etapas de tratamento e mostrando o motivo de cada decisão, como, tons de cinza, recorte, redução de tamanho, suavização, normalização e visualização de bordas.

Depois passei a lógica principal para `processamento_imagem.py`, porque o código que o ROS executa precisa estar em um script Python comum. Nesse arquivo eu deixei a visão computacional separada do controle da tartaruga.

Por último criei o nó `desenha_tartaruga_node.py`, que lê os pontos gerados pelo processamento e controla o `turtlesim` usando seus comandos básicos `cmd_vel`, `pose`, `set_pen` e `teleport_absolute`.

## Pipeline de processamento

A imagem do cachorro é carregada com OpenCV apenas na etapa de leitura. O restante do processamento foi feito com `NumPy`. Para uma explicação mais detalhada, deve-se seguir para o arquivo `tratamento_imagem_cachorro.ipynb`, mas a versão que alimenta o ROS está no script `turtle_draw/processamento_imagem.py`.

No script, eu organizei o processamento em funções menores para conseguir defender cada etapa separadamente. A função principal é `gerar_caminho_do_cachorro`, que recebe o caminho da imagem e devolve uma lista de pontos já no sistema de coordenadas do `turtlesim`. Antes disso, a função `preparar_imagem_para_desenho` concentra a parte de tratamento da imagem sendo, leitura, cinza, recorte, redimensionamento, suavização e normalização.

A parte mais importante para deixar o desenho limpo está em `criar_mascara_do_cachorro`. Nessa etapa eu transformo a imagem tratada em uma máscara binária do cachorro e depois uso operações morfológicas implementadas manualmente. O fechamento ajuda a juntar pequenas quebras da lateral do corpo, enquanto a abertura remove sujeiras pequenas que poderiam virar ruídos no desenho.

Também preencho os buracos internos da máscara para reduzir detalhes de pelo, sombra e textura. Isso deixa o resultado mais parecido com uma silhueta, que é mais adequada para o `turtlesim`, já que a tartaruga desenha com uma linha contínua. Além disso, removo manualmente uma região de sombra no canto inferior esquerdo, porque ela estava sendo interpretada como parte do cachorro e criava um contorno falso.

O fluxo principal é:

1. Eu carrego a imagem e converto de BGR para RGB.
2. Converto para tons de cinza usando pesos perceptuais.
3. Recorto a região onde o cachorro aparece para diminuir fundo vazio.
4. Reduzo a resolução com interpolação bilinear implementada manualmente.
5. Aplico um filtro gaussiano manual para suavizar ruído de pelo e sombra.
6. Normalizo o contraste por percentis.
7. Crio uma máscara do cachorro usando limiar.
8. Uso operações morfológicas para limpar a máscara.
9. Extraio a borda externa da máscara.
10. Ordeno os pontos da borda para formar um caminho.
11. Mapeio os pixels para o espaço `0..11` do `turtlesim`.

Algumas das minhas escolhas foram específicas para esta imagem. Por exemplo, eu removi uma sombra inferior esquerda porque ela estava virando uma espécie de "rabo" falso quando o `turtlesim` estava desenhando.

## Controle da tartaruga

O nó `desenha_tartaruga_node.py` recebe o caminho já pronto. Antes de desenhar, eu desligo a caneta, teleporto a tartaruga para o primeiro ponto e só depois ligo a caneta. Fiz isso para evitar uma linha indesejada atravessando a tela.

O controle acontece em cima de três recursos principais do `turtlesim`:

- `/turtle1/pose`: eu uso para saber onde a tartaruga está e qual é sua orientação atual;
- `/turtle1/cmd_vel`: eu publico velocidades lineares e angulares para mover a tartaruga;
- `/turtle1/set_pen` e `/turtle1/teleport_absolute`: eu uso para controlar a caneta e posicionar a tartaruga no início do desenho.

Eu tratei a preparação do desenho como uma pequena máquina de estados. Primeiro o nó espera os serviços do `turtlesim` ficarem disponíveis. Depois ele desliga a caneta, teleporta para o primeiro ponto e liga a caneta novamente. Só depois disso o estado muda para `desenhando`.

Durante o desenho, a tartaruga sempre olha para o próximo ponto do caminho e usa um controle proporcional simples:

- se está longe do ponto, anda mais;
- se está virada para o lado errado, gira mais;
- quando chega perto o suficiente, passa para o próximo ponto.

Na prática, para cada ponto eu calculo a diferença entre a posição atual da tartaruga e o alvo. Com essa diferença eu obtenho a distância e o ângulo desejado. A velocidade linear depende da distância, e a velocidade angular depende do erro entre o ângulo atual da tartaruga e o ângulo até o alvo.

Também limitei as velocidades máximas para o movimento não ficar agressivo demais. Se o erro angular está muito alto, eu reduzo a velocidade linear para a tartaruga girar primeiro e evitar curvas muito abertas.

Essa parte é necessária porque a borda detectada é apenas uma lista de coordenadas. Para virar desenho no simulador, eu preciso transformar essas coordenadas em movimento físico da tartaruga ao longo do tempo.

## Estrutura

```text
.
├── dog_img/dog.jpg
├── tratamento_imagem_cachorro.ipynb
├── turtle_draw/
│   ├── processamento_imagem.py
│   └── desenha_tartaruga_node.py   
├── package.xml
├── setup.py
└── setup.cfg
```

## Como rodar

Ative o ambiente ROS (macOS):

```bash
# precisa ter baixado micromamba antes
micromamba activate ros_env
```

Na raiz do projeto:

```bash
cd /Users/enzopiolcerutti/Documents/Inteli/turtle-draw
colcon build --symlink-install
source install/setup.zsh
```

Para testar só o processamento da imagem:

```bash
ros2 run turtle_draw processa_imagem
```

Para abrir o simulador:

```bash
ros2 run turtlesim turtlesim_node
```

Em outro terminal, com o mesmo ambiente ativado e o workspace carregado:

```bash
micromamba activate ros_env
cd /Users/enzopiolcerutti/Documents/Inteli/turtle-draw
source install/setup.zsh
ros2 run turtle_draw desenha_tartaruga
```
