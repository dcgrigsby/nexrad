import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js';

const app = document.getElementById('app');
const picker = document.getElementById('file-picker');

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x050505);

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, 10_000_000);
camera.position.set(0, -250000, 125000);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(window.innerWidth, window.innerHeight);
app.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.screenSpacePanning = true;

const loader = new PLYLoader();
let currentPoints = null;

function fitCameraToGeometry(geometry) {
  geometry.computeBoundingSphere();
  const sphere = geometry.boundingSphere;
  if (!sphere) return;
  controls.target.copy(sphere.center);
  camera.position.copy(sphere.center).add(new THREE.Vector3(0, -sphere.radius * 1.8, sphere.radius * 0.8));
  controls.update();
}

function renderGeometry(geometry) {
  if (!geometry.getAttribute('color')) {
    const count = geometry.getAttribute('position').count;
    const colors = new Float32Array(count * 3);
    colors.fill(1.0);
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  }

  const material = new THREE.PointsMaterial({
    size: 250,
    sizeAttenuation: true,
    vertexColors: true,
  });

  if (currentPoints) {
    scene.remove(currentPoints);
    currentPoints.geometry.dispose();
    currentPoints.material.dispose();
  }

  currentPoints = new THREE.Points(geometry, material);
  scene.add(currentPoints);
  fitCameraToGeometry(geometry);
}

function loadFromUrl(url) {
  loader.load(url, (geometry) => renderGeometry(geometry), undefined, (err) => {
    // eslint-disable-next-line no-console
    console.error('Failed to load PLY from URL:', err);
  });
}

function loadFromFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const geometry = loader.parse(reader.result);
    renderGeometry(geometry);
  };
  reader.readAsArrayBuffer(file);
}

picker.addEventListener('change', (event) => {
  const file = event.target.files?.[0];
  if (file) loadFromFile(file);
});

const fileParam = new URLSearchParams(window.location.search).get('file');
if (fileParam) {
  loadFromUrl(fileParam);
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

animate();
