# 🏛️ OneCalama API - Backend de Gestión Ciudadana

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-REST_Framework-092E20.svg?logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Data_Tier-316192.svg?logo=postgresql&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-EC2_Deployed-232F3E.svg?logo=amazon-aws&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-Data_Analysis-150458.svg?logo=pandas&logoColor=white)

Prototipo funcional (TRL-3) de una API RESTful desarrollada para la Municipalidad de Calama. Este sistema centraliza, geolocaliza y procesa las denuncias vecinales, optimizando los tiempos de respuesta del municipio y proveyendo un motor de analítica para la toma de decisiones territoriales.

## 🚀 Arquitectura y Decisiones Técnicas

Este proyecto abandona el patrón tradicional de "vistas obesas" (Fat Views) implementando una **arquitectura modular basada en capas de servicios**. 

* **Motor Estadístico Avanzado:** Integración de agregaciones complejas del ORM de Django con **Pandas** para el cálculo dinámico de días hábiles legales, índices de criticidad de juntas vecinales y generación de mapas de calor.
* **Lógica Geoespacial Optimizada:** En lugar de sobrecargar la base de datos con extensiones pesadas, el cálculo de distancias y la asignación territorial se procesan a nivel de servidor utilizando algoritmos matemáticos en Python puro (**Fórmula de Haversine**).
* **Seguridad y Control de Accesos:** Implementación de autenticación mediante tokens **JWT** y un control de acceso basado en roles (RBAC) estricto (Ciudadano, Operador Municipal, Administrador).
* **Gestión Multimedia en la Nube:** Integración directa con **Cloudinary** para el almacenamiento, optimización y entrega persistente de las evidencias fotográficas adjuntas a las denuncias.
* **Trazabilidad Continua:** Diseño de un esquema de auditoría inmutable (`HistorialModificaciones`) que registra cada cambio de estado en los flujos de trabajo municipales (Kanban interno).

## 🗂️ Estructura del Core (Servicios)

La lógica de negocio compleja está abstraída en la capa `services/` para garantizar la escalabilidad y facilitar el testing:
- `geo_service.py`: Cálculos de geolocalización y asignación de entidades territoriales.
- `statistics_service.py`: Análisis de eficiencia, plazos legales y métricas del Dashboard.
- `media_service.py`: Orquestación de subida y eliminación de activos en Cloudinary.
- `report_service.py`: Generación automatizada de reportes exportables (PDF/Excel).

## 🛠️ Instalación y Despliegue Local

Sigue estos pasos para levantar el entorno de desarrollo de la API:

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/SCarrizoZ/BackendMunicipalidadAWS.git](https://github.com/SCarrizoZ/BackendMunicipalidadAWS.git)
   cd BackendMunicipalidadAWS
   ```

2. **Crear y activar el entorno virtual:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno:**
   Crea un archivo `.env` en el directorio raíz asegurándote de incluir tus credenciales de base de datos, clave secreta JWT y URL de Cloudinary.

5. **Ejecutar migraciones de Base de Datos:**
   ```bash
   python manage.py migrate
   ```

6. **Iniciar el servidor de desarrollo:**
   ```bash
   python manage.py runserver
   ```

## ☁️ Infraestructura de Producción
El prototipo fue diseñado para operar en un entorno Cloud, con la base de datos y la aplicación desplegadas en instancias de **Amazon Web Services (AWS EC2)**, gestionando el tráfico entrante mediante configuraciones de seguridad de red (VPC/Security Groups).

---
**Desarrollado y Orquestado por:** [Sebastián Carrizo Zuleta](https://github.com/SCarrizoZ) | Backend Developer & Cloud Ops Junior
