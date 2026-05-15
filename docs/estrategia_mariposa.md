# Estrategia de Opciones: La Mariposa y Metodología de la Escuelita

Este documento detalla el enfoque de trading de opciones basado en las enseñanzas de Francisco Mancuso y la "Escuelita de Opciones", centrándose en la gestión de riesgo y la estructura de la Mariposa.

## 1. Pilares Fundamentales
*   **Venta de Tiempo (Theta):** El objetivo es aprovechar la erosión temporal del valor de las opciones.
*   **Probabilidad sobre Predicción:** No se busca adivinar la dirección exacta, sino operar dentro de rangos de probabilidad estadística.
*   **Riesgo Definido:** Preferencia por estructuras donde la pérdida máxima esté limitada y conocida desde el inicio.

## 2. La Estrategia Mariposa (Butterfly Spread)
La Mariposa es una estrategia neutral diseñada para mercados laterales. Se gana dinero si el activo permanece cerca de un precio objetivo.

### Construcción Paso a Paso (Call Butterfly)
Para armar una mariposa con calls:
1.  **Comprar 1 Call** con un strike inferior ($K_1$).
2.  **Vender 2 Calls** con un strike central ($K_2$) $\rightarrow$ *Este es el "corazón" de la mariposa y donde se busca que termine el precio.*
3.  **Comprar 1 Call** con un strike superior ($K_3$).

*Nota: La distancia entre $K_1$ y $K_2$ debe ser la misma que entre $K_2$ y $K_3$.*

### Perfil de Riesgo y Beneficio
*   **Beneficio Máximo:** Se alcanza si el precio del activo es exactamente $K_2$ al vencimiento.
*   **Riesgo Máximo:** Limitado al costo neto pagado por armar la estructura.
*   **Punto de Equilibrio:** Existen dos puntos de equilibrio (uno arriba y otro abajo del strike central).

## 3. Gestión Operativa (Estilo Escuelita)

### Entrada y Selección
*   **Volatilidad:** Idealmente entrar cuando la volatilidad es alta y se espera que baje o se estabilice.
*   **Strikes:** Utilizar el Delta para definir la probabilidad de que el precio termine en el rango deseado.

### Salida y Ajustes
*   **No esperar al vencimiento:** Se recomienda cerrar la operación cuando se ha capturado una parte significativa del beneficio (ej. 50% del máximo).
*   **Gestión de Pérdida:** Definir un stop loss basado en el capital riesgo asignado a la operación.

## 4. Resumen de Implementación
1.  **Análisis:** Evaluar si el activo entrará en una fase lateral.
2.  **Armado:** Ejecutar la compra/venta de las 4 opciones simultáneamente.
3.  **Monitoreo:** Seguir la caída del valor temporal (Theta).
4.  **Cierre:** Salir de la posición al alcanzar el objetivo de ganancia o el límite de pérdida.
