# Operativa de la Mariposa con argoptions: Guía Práctica

Esta guía transforma la teoría de la Mariposa (Butterfly) en un proceso operativo paso a paso utilizando `argoptions`. El objetivo es encontrar el "punto dulce" donde la probabilidad y el costo sean óptimos.

## 1. El Proceso de "Caza" (Hunting)
Encontrar una Mariposa no es un proceso lineal, sino un ciclo de filtrado y rotación hasta que la matemática de la estructura "encaja".

### Paso 1: El Escaneo Inicial (The Wide Scan)
Primero, necesitamos saber qué hay disponible en el mercado.
1. Inicia `argoptions`, ingresa **Raíz** (ej. `GFG`) y **Spot** (ej. `GGAL`).
2. Haz clic en **"Validar con PPI"** para obtener el precio spot actual.
3. Configura el Screening para buscar el "centro" de la mariposa:
   *   `min_delta`: **0.4**
   *   `max_delta`: **0.6**
   *   `min_dte`: **30** / `max_dte`: **45** (Rango ideal para capturar Theta).
4. Ejecuta **"Screen (form)"**.

### 🚩 ¿Qué hacer si el Screen no devuelve resultados? (The Pivot)
Es común que el filtro sea demasiado restrictivo. Si la tabla está vacía, sigue este orden de ajustes:
1.  **Expandir el Rango (Zoom Out):** Cambia los deltas a `0.3` y `0.7`. Busca el contrato que esté más cerca de **0.50**.
2.  **Rotar el Vencimiento (Time Shift):** Ajusta el `min_dte` y `max_dte` (ej. prueba con 15-30 días o 45-60 días). Algunas series tienen más strikes que otras.
3.  **Refrescar la Cadena:** Ejecuta el botón **"Ejecutar chain"** (`c`). A veces el spot se movió y los deltas recalculados cambian la disponibilidad.
4.  **Búsqueda Manual:** Si nada funciona, usa la cadena completa y busca visualmente el strike más cercano al precio Spot actual.

---

## 2. Ejemplo Práctico Walkthrough (Caso GGAL)

**Escenario:** GGAL cotiza a **$4500**. Creemos que el precio se mantendrá lateral el próximo mes.

### A. Identificando el "Pin" (El Centro - $K_2$)
Tras el Screen, encontramos que el contrato **Call 4500** tiene un **Delta de 0.51**. 
$\rightarrow$ Este es nuestro **$K_2$** (Strike Central). Aquí es donde queremos que el precio termine.

### B. Construyendo las "Alas" ($K_1$ y $K_3$)
Para que la mariposa sea simétrica, elegimos una distancia (ej. 200 puntos):
*   **Ala Inferior ($K_1$):** $4500 - 200 = \mathbf{4300}$ (Buscamos la Call 4300).
*   **Ala Superior ($K_3$):** $4500 + 200 = \mathbf{4700}$ (Buscamos la Call 4700).

### C. Calculando el Costo con la Columna `Mid`
Miramos los precios `Mid` en la tabla de `argoptions`:
*   Call 4300 ($K_1$): **$150**
*   Call 4500 ($K_2$): **$80**
*   Call 4700 ($K_3$): **$30**

**Cálculo de entrada (Net Debit):**
$$\text{Costo} = (\text{Compra } K_1 + \text{Compra } K_3) - (2 \times \text{Venta } K_2)$$
$$\text{Costo} = (150 + 30) - (2 \times 80) = 180 - 160 = \mathbf{20 \text{ pesos}}$$

---

## 3. Matriz de Decisiones: ¿Qué estoy buscando?

| Variable | Qué buscar | Por qué |
| :--- | :--- | :--- |
| **Delta** | $\approx 0.50$ en $K_2$ | Maximiza la probabilidad de que el "pico" de ganancia esté en el precio actual. |
| **Bid-Ask Spread** | Bajo ( < 15-20%) | Un spread ancho "se come" la ganancia al entrar y salir. |
| **Volumen** | Presencia en las alas | Si las alas ($K_1, K_3$) no tienen volumen, no podrás cerrar la posición fácilmente. |
| **Mid Price** | Costo bajo vs Ganancia | Buscamos que el costo de armar la estructura sea una fracción pequeña del beneficio potencial. |

## 4. Monitoreo y Red Flags

### El Bucle de Control
Activa el modo **Auto-chain (`w`)** para observar la posición en tiempo real:
*   **Delta Drift:** Si el Delta de $K_2$ pasa de 0.50 a 0.70, el activo se movió. El "pico" de tu mariposa ya no está donde el precio está. Es momento de evaluar el cierre.
*   **Theta Decay:** Observa cómo el valor de las dos opciones vendidas ($K_2$) cae más rápido que el de las compradas.

### 🚩 Red Flags (Señales de Abortar)
*   **Slippage Extremo:** Si el `Ask` de las alas sube repentinamente, el costo de armar la estructura se vuelve prohibitivo.
*   **Gap de Strikes:** Si para mantener la simetría tienes que saltar a un strike con volumen cero, aborta la operación.
*   **Volatilidad Explosiva:** Si la IV (Volatilidad Implícita) sube bruscamente, la mariposa puede comportarse erráticamente antes del vencimiento.
