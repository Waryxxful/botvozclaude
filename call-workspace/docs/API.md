# Call Workspace API - Guía Técnica

Bienvenido/a a la documentación externa de integración de la **Call Workspace API**. 
Esta plataforma fue desarrollada en Python (Django) exponiendo su funcionalidad primaria a través del plugin **Django Ninja**.

Esta guía profundiza en el comportamiento semántico de la arquitectura REST y cómo integrar correctamente estas rutas en tus herramientas de frontend, tableros o pruebas internas.

---

## 1. Patrón Arquitectónico (REST)

Nuestra API se adhiere estructuralmente a un ecosistema RESTful estático.
Todos los endpoints están agrupados bajo el prefijo `/api/v1/`.

Encontrarás 4 pilares fundamentales (Tags):
*   **Calls**: Entidades núcleo (grabaciones/notas). Modos de lectura puros (`GET`).
*   **Campaigns**: Contenedores de agrupación administrativa (`GET`, `POST`, `PUT`, `DELETE`).
*   **Reviews**: Anotaciones manuales para cada Call realizadas por el humano (Upsert `POST`, `GET`).
*   **Processing**: Control manual del motor interno y Healthchecks de la aplicación (`GET`, `POST`).

Para ver al detalle el listado interactivo con sus esquemas, carga el entorno y refiérete al sub-directorio `/api/v1/docs` (Swagger UI). Aquí mostramos una abstracción.

---

## 2. Autenticación, Sesiones y Seguridad

**Método Aplicado:** Cookie Session (`django_auth`)

Al contrario de una API tradicional moderna la cual depende de JWT o llaves OAuth (`Authorization: Bearer <token>`), todo este workspace asume su ambiente integrado nativo. Depende del mecanismo Session-Middleware de Django. 

**¿Qué significa esto para el consumo manual/externo?**
No usamos cabeceras de autorización base. Si deseas automatizar scripts externos mediante Postman/Insomnia, tu primer paso siempre será:
1. Emular el login accediendo al render estático `POST /accounts/login/` enviando `username`, `password` y el campo de seguridad extra que requiere Django `csrfmiddlewaretoken`.
2. Capturar o delegar la administración de la cabecera `Set-Cookie` resultante (en especial el ID `sessionid` y `csrftoken`).
3. Adjuntar la variable a los subsecuentes request REST.

Si un endpoint recibe una petición carente de esta `Session Cookie` o ésta ha caducado, la API responderá inequívocamente con el error genérico global del framework (Usualmente `401 Unauthorized`).

---

## 3. Manejo de Errores Globales

Django-Ninja normaliza y envuelve todo retorno negativo proveniente del backend en dicts JSON identificables por HTTP Status Codes consistentes.

*   `400 Bad Request`: Principalmente problemas de validación provistos por **Pydantic**. Ocurre cuando invocas un controlador de mutaciones (`POST`/`PUT`) y uno de los campos falta, posee un tipo erróneo, o falla las limitantes de serialización.

    *Típicamente retorna un array `detail` con cada error detectado e indicando el path.*
    ```json
    {
      "detail": [
        {
          "loc": ["body", "ftp_directory"],
          "msg": "field required",
          "type": "value_error.missing"
        }
      ]
    }
    ```

*   `401 Unauthorized`: Denegación pura o pérdida de sesión por caducación.

*   `404 Not Found`: Invocado deliberadamente (usando `get_object_or_404` internamente) cuando una ruta por `id` llama a un registro faltante. Ejemplo: `/api/v1/calls/999/` si sólo existen 5 `Call`.
    
    *Respuesta genérica constante:*
    ```json
    {
      "detail": "Not Found"
    }
    ```

*   `500 Internal Server Error`: Comúnmente ligado a una fallo inexplorado en la base de datos o fallo asíncrono con Redis. No es parseado y requerirá intervención o revisión del logger de la terminal del Docker Gunicorn.

---

## 4. Paginación y Filtrado

Para efectos de eficiencia rápida, la API soporta Query Params (`?query=value`) limitados dentro del agrupador Calls para aligerar la transferencia JSON antes de la UI de cliente.

**Buscado general de llamadas:**
`GET /api/v1/calls/` devolverá una lista optimizada de campos.

*   Para acotar bajo campaña:
    ```http
    GET /api/v1/calls/?campaign_id=3
    ```
*   Para acotar por estado (Por ejemplo las que fracasaron del LLM):
    ```http
    GET /api/v1/calls/?status=error
    ```

Dichas variables (`campaign_id`, `status`) se declaran como opcionales en el controlador de la ruta interactiva, donde podrás probarlas en el Swagger UI.