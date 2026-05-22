import math
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from turtlesim.msg import Pose
from turtlesim.srv import SetPen, TeleportAbsolute

from turtle_draw.processamento_imagem import gerar_caminho_do_cachorro


class DesenhistaTartaruga(Node):
    def __init__(self):
        super().__init__("desenhista_tartaruga")

        self.declare_parameter("imagem", "dog_img/dog.jpg")
        self.declare_parameter("velocidade_linear_maxima", 2.0)
        self.declare_parameter("velocidade_angular_maxima", 5.0)
        self.declare_parameter("tolerancia_distancia", 0.08)

        # Eu gero o caminho uma vez no inicio para o no so se preocupar em controlar a tartaruga.
        caminho_imagem = Path(self.get_parameter("imagem").value)
        self.caminho = gerar_caminho_do_cachorro(caminho_imagem)
        self.indice_alvo = 0
        self.pose_atual = None
        self.estado = "aguardando_pose"
        self.chamada_pendente = None

        self.velocidade_linear_maxima = float(self.get_parameter("velocidade_linear_maxima").value)
        self.velocidade_angular_maxima = float(self.get_parameter("velocidade_angular_maxima").value)
        self.tolerancia_distancia = float(self.get_parameter("tolerancia_distancia").value)

        # Estes topicos e servicos sao os pontos de contato padrao com o turtlesim.
        self.publicador_velocidade = self.create_publisher(Twist, "/turtle1/cmd_vel", 10)
        self.assinante_pose = self.create_subscription(Pose, "/turtle1/pose", self.receber_pose, 10)
        self.cliente_caneta = self.create_client(SetPen, "/turtle1/set_pen")
        self.cliente_teleporte = self.create_client(TeleportAbsolute, "/turtle1/teleport_absolute")
        self.temporizador = self.create_timer(0.03, self.controlar_movimento)

        self.get_logger().info(f"Caminho carregado com {len(self.caminho)} pontos.")

    def receber_pose(self, mensagem):
        self.pose_atual = mensagem

    def criar_requisicao_caneta(self, ligada):
        # Eu uso caneta branca para ficar visivel no fundo azul do turtlesim.
        requisicao = SetPen.Request()
        requisicao.r = 255
        requisicao.g = 255
        requisicao.b = 255
        requisicao.width = 2
        requisicao.off = 0 if ligada else 1
        return requisicao

    def criar_requisicao_teleporte(self, x, y, theta=0.0):
        requisicao = TeleportAbsolute.Request()
        requisicao.x = float(x)
        requisicao.y = float(y)
        requisicao.theta = float(theta)
        return requisicao

    def chamada_terminou(self):
        return self.chamada_pendente is not None and self.chamada_pendente.done()

    def preparar_desenho(self):
        if len(self.caminho) == 0:
            self.get_logger().error("Nenhum ponto foi gerado para desenhar.")
            rclpy.shutdown()
            return

        if self.estado == "aguardando_pose":
            # Antes de desenhar, eu espero os servicos existirem para evitar erro de chamada.
            if not self.cliente_caneta.wait_for_service(timeout_sec=0.1):
                self.get_logger().info("Aguardando /turtle1/set_pen...")
                return
            if not self.cliente_teleporte.wait_for_service(timeout_sec=0.1):
                self.get_logger().info("Aguardando /turtle1/teleport_absolute...")
                return

            self.chamada_pendente = self.cliente_caneta.call_async(
                self.criar_requisicao_caneta(False)
            )
            self.estado = "desligando_caneta"
            return

        if self.estado == "desligando_caneta" and self.chamada_terminou():
            # Eu teleporto com a caneta levantada para nao riscar uma linha ate o primeiro ponto.
            primeiro_x, primeiro_y = self.caminho[0]
            self.chamada_pendente = self.cliente_teleporte.call_async(
                self.criar_requisicao_teleporte(primeiro_x, primeiro_y)
            )
            self.estado = "indo_para_inicio"
            return

        if self.estado == "indo_para_inicio" and self.chamada_terminou():
            self.chamada_pendente = self.cliente_caneta.call_async(
                self.criar_requisicao_caneta(True)
            )
            self.estado = "ligando_caneta"
            return

        if self.estado == "ligando_caneta" and self.chamada_terminou():
            # Depois que a caneta liga, o controle comeca a perseguir o segundo ponto do caminho.
            self.indice_alvo = 1
            self.estado = "desenhando"
            self.get_logger().info("Desenho iniciado.")

    def controlar_movimento(self):
        if self.pose_atual is None:
            return

        if self.estado != "desenhando":
            self.preparar_desenho()
            return

        if self.indice_alvo >= len(self.caminho):
            self.publicador_velocidade.publish(Twist())
            self.get_logger().info("Desenho finalizado.")
            rclpy.shutdown()
            return

        alvo_x, alvo_y = self.caminho[self.indice_alvo]
        diferenca_x = float(alvo_x) - self.pose_atual.x
        diferenca_y = float(alvo_y) - self.pose_atual.y
        distancia = math.hypot(diferenca_x, diferenca_y)

        if distancia < self.tolerancia_distancia:
            # Quando chego perto o suficiente, considero o ponto cumprido e busco o proximo.
            self.indice_alvo += 1
            return

        angulo_alvo = math.atan2(diferenca_y, diferenca_x)
        erro_angulo = normalizar_angulo(angulo_alvo - self.pose_atual.theta)

        comando = Twist()
        # O controle e proporcional: quanto maior o erro, maior a velocidade/giro.
        comando.linear.x = min(self.velocidade_linear_maxima, 2.2 * distancia)
        comando.angular.z = limitar(
            6.0 * erro_angulo,
            -self.velocidade_angular_maxima,
            self.velocidade_angular_maxima,
        )

        if abs(erro_angulo) > 0.8:
            comando.linear.x = 0.2

        self.publicador_velocidade.publish(comando)


def limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def normalizar_angulo(angulo):
    while angulo > math.pi:
        angulo -= 2 * math.pi
    while angulo < -math.pi:
        angulo += 2 * math.pi
    return angulo


def main(args=None):
    rclpy.init(args=args)
    no = DesenhistaTartaruga()
    rclpy.spin(no)


if __name__ == "__main__":
    main()
