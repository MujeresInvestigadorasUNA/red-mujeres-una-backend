"""
Ejemplos de cómo el FRONTEND debe enviar los datos para registro CON imagen.
"""

# ============================================================================
# OPCIÓN 1: JavaScript/Fetch API (Recomendado)
# ============================================================================

/*
Ejemplo en JavaScript para enviar datos de registro con imagen:
*/

async function registerUserWithImage(userData, imageFile) {
  // Crear FormData para multipart/form-data
  const formData = new FormData();
  
  // Agregar campos de texto
  formData.append('email', userData.email);
  formData.append('password', userData.password);
  formData.append('first_name', userData.firstName);
  formData.append('last_name', userData.lastName);
  formData.append('user_type_id', userData.userTypeId); // 1=Usuario, 2=Investigadora
  
  // Agregar archivo (OPCIONAL)
  if (imageFile) {
    formData.append('photo', imageFile);  // imageFile es un File object
  }

  try {
    const response = await fetch('http://localhost:8000/api/v1/users/register', {
      method: 'POST',
      body: formData,  // NO poner Content-Type: FastAPI lo detecta automáticamente
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }

    const result = await response.json();
    console.log('✅ Usuario registrado:', result);
    
    // Guardar token
    localStorage.setItem('access_token', result.access_token);
    
    return result;
  } catch (error) {
    console.error('❌ Error:', error.message);
    throw error;
  }
}

// Uso:
/*
const userData = {
  email: 'maria@example.com',
  password: 'MiClaveSegura123',
  firstName: 'María',
  lastName: 'Pérez',
  userTypeId: 2  // Investigadora
};

const imageInput = document.getElementById('photo');
const imageFile = imageInput.files[0];  // Primer archivo seleccionado

registerUserWithImage(userData, imageFile);
*/


// ============================================================================
// OPCIÓN 2: React con Axios
// ============================================================================

import axios from 'axios';

async function registerUserWithImageReact(userData, imageFile) {
  const formData = new FormData();
  
  formData.append('email', userData.email);
  formData.append('password', userData.password);
  formData.append('first_name', userData.firstName);
  formData.append('last_name', userData.lastName);
  formData.append('user_type_id', userData.userTypeId);
  
  if (imageFile) {
    formData.append('photo', imageFile);
  }

  try {
    const response = await axios.post(
      'http://localhost:8000/api/v1/users/register',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    );

    console.log('✅ Usuario registrado:', response.data);
    localStorage.setItem('access_token', response.data.access_token);
    return response.data;
  } catch (error) {
    console.error('❌ Error:', error.response?.data?.detail || error.message);
    throw error;
  }
}

// Uso en componente React:
/*
const [formData, setFormData] = useState({
  email: '',
  password: '',
  firstName: '',
  lastName: '',
  userTypeId: 1
});

const handleFileChange = (e) => {
  setPhotoFile(e.target.files[0]);
};

const handleSubmit = async (e) => {
  e.preventDefault();
  await registerUserWithImageReact(formData, photoFile);
};

return (
  <form onSubmit={handleSubmit}>
    <input 
      type="email" 
      placeholder="Email"
      onChange={(e) => setFormData({...formData, email: e.target.value})}
    />
    <input type="password" placeholder="Password" />
    <input type="text" placeholder="First Name" />
    <input type="text" placeholder="Last Name" />
    <select>
      <option value={1}>Usuario Normal</option>
      <option value={2}>Investigadora</option>
    </select>
    <input type="file" accept="image/*" onChange={handleFileChange} />
    <button type="submit">Registrar</button>
  </form>
);
*/


// ============================================================================
// OPCIÓN 3: cURL (para testing)
// ============================================================================

/*
curl -X POST "http://localhost:8000/api/v1/users/register" \
  -F "email=maria@example.com" \
  -F "password=MiClaveSegura123" \
  -F "first_name=María" \
  -F "last_name=Pérez" \
  -F "user_type_id=2" \
  -F "photo=@/ruta/a/imagen.jpg"

Respuesta esperada:
{
  "success": true,
  "user": {
    "id": 1,
    "email": "maria@example.com",
    "first_name": "María",
    "last_name": "Pérez",
    "photo_url": "https://rdmaunaadmin.blob.core.windows.net/images/users/profile-pictures/imagen_20260120_150235.jpg",
    "user_type_id": 2
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
*/


// ============================================================================
// OPCIÓN 4: Actualizar foto de perfil (usuario existente)
// ============================================================================

async function updateProfilePicture(userId, imageFile) {
  const formData = new FormData();
  formData.append('photo', imageFile);

  try {
    const response = await fetch(
      `http://localhost:8000/api/v1/users/${userId}/profile-picture`,
      {
        method: 'POST',
        body: formData,
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      }
    );

    if (!response.ok) {
      throw new Error('Failed to update profile picture');
    }

    const result = await response.json();
    console.log('✅ Foto actualizada:', result.photo_url);
    return result;
  } catch (error) {
    console.error('❌ Error:', error);
    throw error;
  }
}

// cURL:
/*
curl -X POST "http://localhost:8000/api/v1/users/123/profile-picture" \
  -H "Authorization: Bearer <tu-token>" \
  -F "photo=@/ruta/a/imagen.jpg"
*/


// ============================================================================
// VALIDACIONES EN EL FRONTEND (RECOMENDADO)
// ============================================================================

function validateImage(file) {
  // Validar tipo
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
  if (!allowedTypes.includes(file.type)) {
    throw new Error(`Tipo no permitido. Usa: ${allowedTypes.join(', ')}`);
  }

  // Validar tamaño (máximo 5MB)
  const maxSize = 5 * 1024 * 1024;
  if (file.size > maxSize) {
    throw new Error(`Imagen muy grande. Máximo 5MB, tu archivo: ${(file.size / 1024 / 1024).toFixed(2)}MB`);
  }

  // Validar dimensiones (opcional, requiere cargar la imagen)
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        if (img.width > 5000 || img.height > 5000) {
          reject(new Error('Dimensiones muy grandes. Máximo 5000x5000 píxeles'));
        } else {
          resolve(true);
        }
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

// Uso:
/*
const imageInput = document.getElementById('photo');
imageInput.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  try {
    await validateImage(file);
    console.log('✅ Imagen válida');
  } catch (error) {
    console.error('❌ Validación fallida:', error.message);
  }
});
*/


// ============================================================================
// FLUJO COMPLETO EN REACT CON VALIDACIÓN
// ============================================================================

import React, { useState } from 'react';
import axios from 'axios';

function RegisterForm() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    firstName: '',
    lastName: '',
    userTypeId: 1
  });
  const [photoFile, setPhotoFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'userTypeId' ? parseInt(value) : value
    }));
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      // Validar imagen
      const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
      if (!allowedTypes.includes(file.type)) {
        throw new Error('Tipo de imagen no válido');
      }

      const maxSize = 5 * 1024 * 1024;
      if (file.size > maxSize) {
        throw new Error('Imagen muy grande (máximo 5MB)');
      }

      setPhotoFile(file);
      setError('');
    } catch (err) {
      setError(err.message);
      setPhotoFile(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const formDataToSend = new FormData();
      formDataToSend.append('email', formData.email);
      formDataToSend.append('password', formData.password);
      formDataToSend.append('first_name', formData.firstName);
      formDataToSend.append('last_name', formData.lastName);
      formDataToSend.append('user_type_id', formData.userTypeId);
      
      if (photoFile) {
        formDataToSend.append('photo', photoFile);
      }

      const response = await axios.post(
        'http://localhost:8000/api/v1/users/register',
        formDataToSend,
        {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        }
      );

      // Éxito
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('user', JSON.stringify(response.data.user));
      setSuccess(true);
      
      // Redirigir o actualizar estado
      console.log('✅ Usuario registrado:', response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrar');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label>Email:</label>
        <input
          type="email"
          name="email"
          value={formData.email}
          onChange={handleInputChange}
          required
        />
      </div>

      <div>
        <label>Contraseña:</label>
        <input
          type="password"
          name="password"
          value={formData.password}
          onChange={handleInputChange}
          required
        />
      </div>

      <div>
        <label>Nombre:</label>
        <input
          type="text"
          name="firstName"
          value={formData.firstName}
          onChange={handleInputChange}
          required
        />
      </div>

      <div>
        <label>Apellido:</label>
        <input
          type="text"
          name="lastName"
          value={formData.lastName}
          onChange={handleInputChange}
          required
        />
      </div>

      <div>
        <label>Tipo:</label>
        <select name="userTypeId" value={formData.userTypeId} onChange={handleInputChange}>
          <option value={1}>Usuario Normal</option>
          <option value={2}>Investigadora</option>
        </select>
      </div>

      <div>
        <label>Foto de perfil (opcional):</label>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileChange}
        />
        {photoFile && <p>✅ {photoFile.name}</p>}
      </div>

      {error && <p style={{ color: 'red' }}>❌ {error}</p>}
      {success && <p style={{ color: 'green' }}>✅ Registrado exitosamente</p>}

      <button type="submit" disabled={loading}>
        {loading ? 'Registrando...' : 'Registrar'}
      </button>
    </form>
  );
}

export default RegisterForm;
