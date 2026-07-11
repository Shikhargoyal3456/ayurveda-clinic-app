import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js';

let scene, camera, renderer, controls;
let heart, particles;

function init() {
    const container = document.getElementById('three-container');
    if (!container) return;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);

    camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 0, 6);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enableZoom = false;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.5;

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const pointLight1 = new THREE.PointLight(0x2563eb, 1, 100);
    pointLight1.position.set(5, 5, 5);
    scene.add(pointLight1);

    const pointLight2 = new THREE.PointLight(0x8b5cf6, 1, 100);
    pointLight2.position.set(-5, -5, 5);
    scene.add(pointLight2);

    createHeart();
    createParticles();

    window.addEventListener('resize', onWindowResize);
    animate();
}

function createHeart() {
    const x = 0, y = 0;
    const heartShape = new THREE.Shape();
    heartShape.moveTo(x + 0, y + 0.5);
    heartShape.bezierCurveTo(x + 0, y + 0.5, x + 0.4, y + 0.9, x + 0.8, y + 0.5);
    heartShape.bezierCurveTo(x + 1.1, y + 0.2, x + 0.8, y - 0.1, x + 0.5, y - 0.2);
    heartShape.lineTo(x + 0, y - 0.6);
    heartShape.lineTo(x - 0.5, y - 0.2);
    heartShape.bezierCurveTo(x - 0.8, y - 0.1, x - 1.1, y + 0.2, x - 0.8, y + 0.5);
    heartShape.bezierCurveTo(x - 0.4, y + 0.9, x + 0, y + 0.5, x + 0, y + 0.5);

    const extrudeSettings = {
        depth: 0.3,
        bevelEnabled: true,
        bevelThickness: 0.1,
        bevelSize: 0.1,
        bevelOffset: 0,
        bevelSegments: 8
    };

    const geometry = new THREE.ExtrudeGeometry(heartShape, extrudeSettings);
    const material = new THREE.MeshPhysicalMaterial({
        color: 0x2563eb,
        metalness: 0.3,
        roughness: 0.4,
        transmission: 0.7,
        transparent: true,
        opacity: 0.9
    });

    heart = new THREE.Mesh(geometry, material);
    heart.scale.set(1.5, 1.5, 1);
    heart.position.set(0, 0, 0);
    scene.add(heart);
}

function createParticles() {
    const particleCount = 500;
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
        positions[i] = (Math.random() - 0.5) * 20;
        positions[i + 1] = (Math.random() - 0.5) * 20;
        positions[i + 2] = (Math.random() - 0.5) * 20;

        const color = new THREE.Color();
        color.setHSL(0.6 + Math.random() * 0.2, 0.7, 0.6);
        colors[i] = color.r;
        colors[i + 1] = color.g;
        colors[i + 2] = color.b;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
        size: 0.08,
        vertexColors: true,
        transparent: true,
        opacity: 0.8
    });

    particles = new THREE.Points(geometry, material);
    scene.add(particles);
}

function onWindowResize() {
    const container = document.getElementById('three-container');
    if (!container || !camera || !renderer) return;

    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
}

let time = 0;
function animate() {
    requestAnimationFrame(animate);
    time += 0.01;

    if (heart) {
        heart.rotation.y += 0.01;
        const scale = 1 + Math.sin(time * 3) * 0.1;
        heart.scale.set(scale * 1.5, scale * 1.5, scale * 1.5);
    }

    if (particles) {
        particles.rotation.y += 0.001;
        particles.rotation.x += 0.0005;
    }

    controls.update();
    renderer.render(scene, camera);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
