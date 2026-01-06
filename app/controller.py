import viktor as vkt


class Parametrization(vkt.Parametrization):
    pass


class Controller(vkt.Controller):
    parametrization = Parametrization
