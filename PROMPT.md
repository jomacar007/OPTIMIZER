# PROMPT — Portfolio Optimizer (versión final, 4 modos)

Quiero desarrollar un proyecto completamente independiente llamado
**Portfolio Optimizer**.

## Objetivo

Construir una aplicación en Python + Streamlit que calcule cómo repartir
un capital entre los tres resultados de un mercado deportivo tipo
Polymarket:

- Equipo A
- Empate
- Equipo B

Cada resultado tiene un precio YES entre 0 y 1. El usuario ingresa:

- Precio Equipo A
- Precio Empate
- Precio Equipo B
- Capital disponible

Ejemplo real de referencia:
Equipo A = 0.16, Empate = 0.26, Equipo B = 0.59, Capital = 100 USD.

## Mecánica del mercado (fundamental, no simplificar)

Cada contrato cuesta su precio y paga **1 USD** si ese resultado ocurre,
y 0 USD si no ocurre.

```
acciones = inversión_en_ese_resultado / precio_de_ese_resultado
cobro_si_ese_resultado_gana = acciones * 1 USD
beneficio_en_ese_escenario = cobro_si_ese_resultado_gana - inversión_TOTAL
```

Importante: el beneficio de un escenario siempre resta la inversión
**total** (en los tres resultados juntos), no solo la inversión puesta
en ese resultado. Esta distinción debe quedar clara también en la UI
(columna "Cobro" separada de columna "Ganancia").

## Modos de uso (4 modos obligatorios)

### Modo 1 — Manual (USD)
El usuario introduce manualmente cuánto invertir en A, Empate y B (en
dólares). La app calcula automáticamente, para cada uno de los tres
escenarios posibles:
- acciones compradas
- cobro
- beneficio o pérdida
- ROI

### Modo 2 — Barras de porcentaje
El usuario mueve **tres sliders independientes** (% Equipo A, % Empate,
% Equipo B) que **no necesitan sumar 100**. La app normaliza
automáticamente de forma proporcional para que el reparto en USD sume
exactamente el capital. Ejemplo: si el usuario pone 16 / 26 / 80 (suma
122), se normaliza a aproximadamente 13.1% / 21.3% / 65.6%.

Mostrar siempre: la suma cruda introducida y el resultado ya normalizado.

### Modo 3 — Maximin (3 resultados)
El usuario solo introduce precios y capital. Usar **scipy.optimize.linprog**
(programación lineal real, no heurísticas) para resolver:

```
maximizar   t
sujeto a    t <= beneficio_i(x)   para cada resultado i = A, Empate, B
            x_A + x_Empate + x_B = capital
            x_i >= mínimo_i >= 0   (mínimos opcionales por resultado)
```

Es decir: busca la distribución que **maximiza el peor escenario
posible** entre los tres resultados simultáneamente. Si la suma de los
tres precios es mayor que 1, el resultado óptimo es una pérdida mínima
garantizada e igual en los tres escenarios (no puede convertirse en
ganancia). Si la suma es menor que 1 (arbitraje), debe encontrar un
beneficio garantizado, también igual en los tres.

Permitir mínimos opcionales por resultado (para no dejar ningún
resultado forzosamente en 0 si el usuario no lo desea).

### Modo 4 — Sacrificar un resultado (CRÍTICO, no omitir)
Modela la estrategia real de "ir con el favorito y cubrir parcialmente
el empate, aceptando perder si gana el equipo que creo menos probable".

El usuario:
1. Elige qué resultado sacrifica (A, Empate o B).
2. Fija, con un slider de 0% a 100% del capital, el **monto máximo**
   que está dispuesto a arriesgar en ese resultado sacrificado (puede
   ser 0).

El optimizador (también con `scipy.optimize.linprog`) reparte el
**resto** del capital entre los **otros dos resultados** para maximizar
e igualar su ganancia conjunta — es un maximin restringido a esos dos
resultados, no a los tres. Formulación:

```
Sea s el resultado sacrificado con monto fijo x_s (elegido por el usuario).
Sean j, k los otros dos resultados. capital_restante = capital - x_s.

maximizar   t
sujeto a    t <= x_j/p_j - capital        (beneficio del resultado j)
            t <= x_k/p_k - capital        (beneficio del resultado k)
            x_j + x_k = capital_restante
            x_j, x_k >= 0
```

Notar que el beneficio de j y k sigue restando el capital **total**
invertido (incluyendo lo sacrificado en s, porque ese dinero también
está en juego y se pierde si s no ocurre). El beneficio del resultado
sacrificado se calcula y se muestra aparte (puede ser muy negativo, no
forma parte del objetivo de optimización).

Caso de validación de referencia (debe reproducirse exactamente):
con precios A=0.16, Empate=0.26, B=0.59, capital=100, sacrificando A al
0%, el resultado correcto es: Empate ≈ 30.59 USD, B ≈ 69.41 USD, A = 0,
con ganancia de **+17.65 USD en empate y en B por igual**, y pérdida de
-100 USD si gana A.

## Mostrar resultados (en todos los modos)

Tabla con columnas: Resultado | Inversión | Acciones | Cobro | Ganancia | ROI
para las tres filas: Gana Equipo A / Empate / Gana Equipo B.

Mostrar además, como métricas resumen:
- Inversión total
- Beneficio máximo
- Pérdida máxima
- ROI máximo y ROI mínimo

## Dashboard (Streamlit)

Diseño limpio, sin variables globales, con sidebar y panel principal.

**Sidebar:**
- Capital disponible
- Precio Equipo A, Precio Empate, Precio Equipo B
- Selector de modo (radio button con los 4 modos)
- Controles específicos del modo 3 (mínimos opcionales, en un expander)
- Controles específicos del modo 4 (radio para elegir resultado a
  sacrificar + slider de monto máximo a arriesgar) — estos pueden ir en
  el panel principal si es más natural en Streamlit

**Panel principal:**
- Resumen (métricas)
- Distribución recomendada/utilizada (una métrica por resultado)
- Tabla de resultados por escenario
- Gráfico de barras (Plotly) de ganancia neta por escenario, coloreado
  verde si es positiva y rojo si es negativa
- Gráfico de pastel (Plotly) de la distribución del capital

## Validaciones

- Todos los precios deben ser mayores que 0 y menores que 1.
- El capital debe ser mayor que 0.
- Las inversiones manuales no pueden ser negativas ni superar el capital
  (informar si queda capital sin asignar, no es error).
- Las barras de porcentaje no pueden ser negativas; al menos una debe
  ser mayor que 0 para poder normalizar.
- La suma de los mínimos (modo 3) no puede superar el capital.
- El monto sacrificado (modo 4) debe estar entre 0 y el capital.
- Mostrar siempre mensajes de error claros y en español, usando
  `st.error()`, y detener la ejecución con `st.stop()` cuando hay un
  error bloqueante.

## Arquitectura (módulos separados, obligatorio)

```
portfolio_optimizer/
├── app.py          # Solo interfaz Streamlit: sidebar, layout, llamadas
│                    # a los otros módulos. Sin lógica de cálculo aquí.
├── optimizer.py     # solve_maximin() y solve_maximin_sacrifice(),
│                    # ambas resueltas con scipy.optimize.linprog
├── calculator.py    # compute_scenario_result(): acciones, cobros,
│                    # beneficios y ROI por escenario, dado un reparto
├── plots.py         # build_profit_bar_chart() y build_investment_pie_chart()
│                    # con Plotly
├── utils.py          # MarketPrices, OUTCOME_LABELS, todas las funciones
│                    # validate_*, y normalize_percentages() /
│                    # percentages_to_investments() para el modo 2
├── requirements.txt
└── README.md
```

## Librerías

```
streamlit>=1.32.0
numpy>=1.26.0
pandas>=2.2.0
scipy>=1.12.0
plotly>=5.20.0
```

## Calidad de código (obligatorio)

- Código profesional, con funciones documentadas (docstrings estilo
  Google: Args, Returns, Raises).
- Tipado completo (`from __future__ import annotations`, type hints en
  todas las funciones).
- Separación clara entre lógica de cálculo/optimización (módulos
  `optimizer.py`, `calculator.py`, `utils.py`) y UI (`app.py`).
- Sin variables globales.
- Usar `@dataclass(frozen=True)` para las estructuras de datos
  (`MarketPrices`, `ScenarioResult`, `OptimizationResult`,
  `ValidationResult`).

## Resultado esperado

Al ejecutar:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Debe abrirse una calculadora interactiva con sidebar para precios,
capital y selector de modo, donde el usuario pueda:
1. Repartir manualmente en USD.
2. Repartir con tres barras de porcentaje normalizadas.
3. Obtener el reparto maximin óptimo entre los tres resultados
   (resuelto con scipy.optimize, no con heurísticas).
4. Sacrificar deliberadamente un resultado y obtener el reparto maximin
   óptimo entre los otros dos (también resuelto con scipy.optimize).

En todos los modos debe verse la tabla completa de acciones, cobros,
ganancias y ROI por escenario, junto con los gráficos de barras y de
pastel.

No simplifiques la optimización ni el modo 4: ambos deben resolverse
con `scipy.optimize.linprog` de forma matemática, formulando
explícitamente las variables de decisión, restricciones y función
objetivo como se describe arriba. Deja el proyecto listo para futuras
ampliaciones (por ejemplo, un modo de "valor esperado" con
probabilidades propias del usuario, distintas de las del mercado).
