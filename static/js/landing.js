(() => {
  const canvas = document.getElementById("scene");

  function bootFallback() {
    document.body.classList.add("no-webgl");
  }

  if (!canvas || !window.THREE) {
    bootFallback();
    return;
  }

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.1, 100);
  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: "high-performance"
  });

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.position.set(0, 0, 9);

  const group = new THREE.Group();
  scene.add(group);

  const colors = [0x4cc9f0, 0x8b5cf6, 0xf15bb5, 0x66f2b6];
  const geometries = [
    new THREE.IcosahedronGeometry(0.7, 1),
    new THREE.TorusKnotGeometry(0.42, 0.12, 82, 10),
    new THREE.OctahedronGeometry(0.62, 0),
    new THREE.TetrahedronGeometry(0.72, 0)
  ];

  // Floating forms nod to yantra geometry and keep the foreground readable.
  for (let i = 0; i < 18; i += 1) {
    const material = new THREE.MeshStandardMaterial({
      color: colors[i % colors.length],
      transparent: true,
      opacity: 0.34,
      roughness: 0.38,
      metalness: 0.45
    });
    const mesh = new THREE.Mesh(geometries[i % geometries.length], material);
    mesh.position.set(
      (Math.random() - 0.5) * 15,
      (Math.random() - 0.5) * 8,
      (Math.random() - 0.5) * 8
    );
    mesh.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
    mesh.scale.setScalar(0.55 + Math.random() * 0.95);
    mesh.userData = {
      drift: 0.2 + Math.random() * 0.55,
      spin: 0.002 + Math.random() * 0.006,
      startY: mesh.position.y
    };
    group.add(mesh);
  }

  const particleCount = window.innerWidth < 720 ? 420 : 760;
  const particleGeometry = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);

  for (let i = 0; i < particleCount * 3; i += 3) {
    positions[i] = (Math.random() - 0.5) * 18;
    positions[i + 1] = (Math.random() - 0.5) * 10;
    positions[i + 2] = (Math.random() - 0.5) * 12;
  }

  particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const particles = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({
      color: 0xbfd7ff,
      size: 0.018,
      transparent: true,
      opacity: 0.58,
      depthWrite: false
    })
  );
  scene.add(particles);

  scene.add(new THREE.AmbientLight(0x9fb7ff, 0.72));

  const keyLight = new THREE.PointLight(0x4cc9f0, 1.75, 28);
  keyLight.position.set(-4, 3, 5);
  scene.add(keyLight);

  const rimLight = new THREE.PointLight(0xf15bb5, 1.15, 24);
  rimLight.position.set(5, -2, 4);
  scene.add(rimLight);

  let pointerX = 0;
  let pointerY = 0;

  window.addEventListener("pointermove", (event) => {
    pointerX = (event.clientX / window.innerWidth - 0.5) * 2;
    pointerY = (event.clientY / window.innerHeight - 0.5) * 2;
  }, { passive: true });

  window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  function animate(time = 0) {
    const t = time * 0.001;

    group.children.forEach((mesh, index) => {
      mesh.rotation.x += mesh.userData.spin;
      mesh.rotation.y += mesh.userData.spin * 1.35;
      mesh.position.y = mesh.userData.startY + Math.sin(t * mesh.userData.drift + index) * 0.34;
    });

    group.rotation.y = t * 0.055 + pointerX * 0.08;
    group.rotation.x = pointerY * 0.045;
    particles.rotation.y = t * 0.018;
    particles.rotation.x = Math.sin(t * 0.2) * 0.035;
    camera.position.x += (pointerX * 0.22 - camera.position.x) * 0.035;
    camera.position.y += (-pointerY * 0.18 - camera.position.y) * 0.035;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);

    if (!prefersReducedMotion) {
      requestAnimationFrame(animate);
    }
  }

  animate();
})();
