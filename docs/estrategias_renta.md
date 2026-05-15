# Estrategias de Renta: El Método de la "Escuelita"

Este documento detalla las estrategias de generación de ingresos (renta) basadas en la metodología de Francisco Mancuso y la Escuelita de Opciones, enfocadas en la probabilidad estadística y la gestión activa.

## 1. Filosofía Operativa: El "Casino" vs el "Jugador"
La Escuelita no busca predecir la dirección exacta del mercado, sino posicionarse como el "casino":
*   **Venta de Probabilidad:** Operar con Deltas bajos ($\approx 0.15$ a $0.30$) para tener una probabilidad de éxito del $70\%$ al $85\%$.
*   **Cosecha de Theta:** Ganar dinero mediante la erosión del valor temporal de las opciones vendidas.
*   **Cierre Temprano:** No esperar al vencimiento. La regla general es cerrar la operación al alcanzar el **30% - 50% del beneficio máximo**.

---

## 2. Estrategias Clave

### A. Iron Condor (La Mariposa Expandida)
Es la estrategia reina para mercados laterales. Crea una "zona de ganancias" en lugar de un punto único.
*   **Construcción:**
    1.  Vende una **Call** (Delta $\approx 0.20$) y compra una **Call** más lejana (Seguro).
    2.  Vende una **Put** (Delta $\approx 0.20$) y compra una **Put** más lejana (Seguro).
*   **Objetivo:** Que el precio termine *entre* las dos opciones vendidas.

### B. Credit Spreads (Alcistas y Bajistas)
Se usan cuando hay un sesgo direccional pero se quiere mantener una alta probabilidad de éxito.
*   **Bull Put Spread (Alcista):** Vender una Put y comprar otra más baja. Ganamos si el precio sube o se queda lateral.
*   **Bear Call Spread (Bajista):** Vender una Call y comprar otra más alta. Ganamos si el precio baja o se queda lateral.

---

## 3. Implementación y Automatización en `argoptions`

Para operar estas estrategias, utilizaremos las herramientas de filtrado de la aplicación para eliminar la subjetividad.

### Flujo de Trabajo para Iron Condor
1.  **Búsqueda de la Zona Superior (Call Side):**
    *   `in_min_delta`: **0.15** / `in_max_delta`: **0.25**.
    *   Ejecuta **Screen**. Selecciona el contrato con el mejor volumen y spread. Este es tu "techo".
2.  **Búsqueda de la Zona Inferior (Put Side):**
    *   Repite el proceso pero filtrando por **Puts** con Delta entre **-0.15 y -0.25**. Este es tu "piso".
3.  **Definición de Seguros:**
    *   Busca contratos con Delta $\approx 0.10$ o menos para limitar el riesgo máximo.

### Gestión de la Operación (Automatización de Salida)
Utiliza la función de **Auto-chain (`w`)** y el **Journal** para aplicar la regla del 30%:
1.  **Cálculo del Máximo:** Al armar la posición, anota el crédito recibido (ej. $100).
2.  **Monitoreo:** Si el valor actual de la estructura para cerrar es de $30 (ganancia de $70), has alcanzado el $70\%$ del beneficio.
3.  **Acción:** Cerrar inmediatamente. No arriesgar la ganancia por el $30\%$ restante.

### El "Roll" (Ajuste de Posición)
Si el precio amenaza con romper una de tus barreras (el Delta de la opción vendida sube a $> 0.40$):
*   **Roll Out:** Cierra la posición actual y ábrela nuevamente para el siguiente mes (compras más tiempo para que el precio regrese).
*   **Roll Up/Down:** Desplaza los strikes en la dirección del movimiento del precio para recuperar la neutralidad.

---

## 4. Recursos y Referencias
Para profundizar en la teoría y ver ejemplos en vivo, se recomienda seguir los canales oficiales de la Escuelita de Opciones:
*   **YouTube:** [Francisco Mancuso / Escuelita de Opciones](https://www.youtube.com/results?search_query=Francisco+Mancuso+escuelita+de+opciones)
*   **Conceptos Clave:** Buscar "Venta de tiempo", "Delta neutral" y "Gestión de spreads".
