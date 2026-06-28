# Portfolio Optimizer v3

Calculadora en Python + Streamlit para repartir capital entre los tres
resultados de un mercado deportivo de tipo Polymarket (Equipo A, Empate,
Equipo B), cada uno con su propio precio YES (entre 0 y 1).

Esta es la versión final, con cuatro modos de cálculo.

## Cómo funciona el mercado

Cada contrato cuesta su precio (entre 0 y 1 USD) y paga **1 USD** si ese
resultado ocurre, y 0 USD si no.

```
acciones = inversión / precio
cobro    = acciones × 1 USD     (si ese resultado ocurre)
beneficio = cobro − inversión total
```

**Importante:** el "cobro" de un escenario no es la ganancia. La
ganancia siempre resta el capital total invertido (en los tres
resultados juntos), no solo lo invertido en ese resultado.

## Los cuatro modos

### 1. Manual (USD)
Tú decides cuánto invertir, en dólares, en cada resultado.

### 2. Barras de porcentaje
Tres sliders independientes (% A, % Empate, % B) que no necesitan sumar
100 — se normalizan automáticamente de forma proporcional.

### 3. Maximin (3 resultados)
Resuelve, con `scipy.optimize.linprog`, el reparto que **maximiza el peor
escenario posible entre los tres resultados a la vez**:

```
maximizar   t
sujeto a    t ≤ beneficio_i(x)   para cada resultado i = A, Empate, B
            x_A + x_Empate + x_B = capital
            x_i ≥ mínimo_i ≥ 0
```

Si la suma de los tres precios es mayor que 1, el mejor resultado posible
es una pérdida mínima garantizada e igual en los tres escenarios. Si la
suma es menor que 1 (arbitraje), encuentra un beneficio garantizado,
también igual en los tres.

### 4. Sacrificar un resultado
Para estrategias del tipo "voy con el favorito y cubro el empate, acepto
perder si gana el equipo que creo menos probable". Tú eliges:

- Qué resultado sacrificas (A, Empate o B).
- Cuánto, como máximo, estás dispuesto a arriesgar ahí (puede ser 0%).

El optimizador reparte el resto del capital entre **los otros dos
resultados** para maximizar e igualar su ganancia conjunta (maximin
restringido a esos dos), dejando la pérdida del resultado sacrificado
acotada al monto que tú fijaste. Matemáticamente:

```
maximizar   t
sujeto a    t ≤ beneficio_j(x)   (resultado no sacrificado 1)
            t ≤ beneficio_k(x)   (resultado no sacrificado 2)
            x_j + x_k = capital − monto_sacrificado
            x_j, x_k ≥ 0
```

## Estructura del proyecto

```
portfolio_optimizer_v3/
├── app.py          # Interfaz Streamlit (sidebar, 4 modos, layout)
├── optimizer.py    # solve_maximin + solve_maximin_sacrifice (scipy.optimize)
├── calculator.py   # Cálculo de acciones, cobros, beneficios y ROI
├── plots.py        # Gráficos con Plotly (barras y distribución)
├── utils.py        # Tipos de datos, validaciones y normalización de %
├── requirements.txt
└── README.md
```

## Instalación y ejecución

```bash
cd portfolio_optimizer_v3
pip install -r requirements.txt
streamlit run app.py
```

Esto abre la app en el navegador, normalmente en `http://localhost:8501`.

## Validaciones

- Todos los precios deben estar estrictamente entre 0 y 1.
- El capital debe ser mayor que 0.
- Las inversiones manuales no pueden ser negativas ni superar el capital.
- Las barras de porcentaje no pueden ser negativas, y al menos una debe
  estar por encima de 0%.
- La suma de los mínimos (modo Maximin) no puede superar el capital.
- El monto sacrificado (modo Sacrificar) debe estar entre 0 y el capital.

## Posibles ampliaciones futuras

- Guardar y comparar varias estrategias lado a lado en la misma pantalla.
- Modo "valor esperado" con probabilidades propias del usuario, distintas
  de las implícitas en los precios del mercado.
- Soporte para mercados con más de 3 resultados.
- Histórico de mercados guardados y carga desde CSV/API de Polymarket.
