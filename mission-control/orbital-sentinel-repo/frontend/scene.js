/* Orbital Sentinel — 3D scene (Three.js)
 *
 * Exposes window.OrbitalScene = { init, setShellStatus, setVisibility, ... }
 * Earth + three orbital shells + instanced satellites/debris + stars.
 */

(function () {
  "use strict";

  const SHELL_KEYS = ["A", "B", "C"];

  // Real-world altitudes (km). Visual radii are stretched so shells are
  // distinguishable; Earth radius is normalized to 1.
  const REAL = {
    earth_km: 6371,
    shell_km: { A: 600, B: 800, C: 1000 },
  };

  // Visual radii — these get over-ridden by setAltitudeExaggeration().
  let visualRadii = { A: 1.42, B: 1.66, C: 1.92 };

  // Cap instance counts for perf — populations are scaled, not 1:1.
  const SAT_CAP = 220;
  const DEB_CAP = 280;

  // --- Three.js scaffolding ----------------------------------------------
  let renderer, scene, camera;
  let earth, atmosphere, starfield;
  const shells = {}; // key -> { sphere, ring, sats, debris, sat_speeds, deb_speeds, sat_axes, deb_axes }
  let clock;
  let autoRotate = true;
  let cameraYaw = 0.4, cameraPitch = 0.2, cameraDist = 5.4;
  let cameraTargetDist = 5.4;
  let cameraTargetYaw = 0.4, cameraTargetPitch = 0.2;
  let raycaster, pointer;
  let shellClickHandler = null;
  let shellHoverHandler = null;
  let hoveredShellKey = null;

  function init(canvas) {
    const THREE = window.THREE;

    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    resize();

    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x05070d, 0.04);

    camera = new THREE.PerspectiveCamera(40, canvas.clientWidth / canvas.clientHeight, 0.1, 200);

    // --- Lights ---
    const ambient = new THREE.AmbientLight(0x9bb8ff, 0.35);
    scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(0xfff2d6, 1.2);
    keyLight.position.set(5, 3, 4);
    scene.add(keyLight);

    const rimLight = new THREE.PointLight(0x6fd2ff, 1.2, 30);
    rimLight.position.set(-6, -2, -4);
    scene.add(rimLight);

    // --- Starfield ---
    starfield = makeStars(THREE, 2200);
    scene.add(starfield);

    // --- Earth ---
    earth = makeEarth(THREE);
    scene.add(earth);

    // --- Atmosphere glow ---
    atmosphere = makeAtmosphere(THREE);
    scene.add(atmosphere);

    // --- Shells ---
    for (const key of SHELL_KEYS) {
      const s = makeShell(THREE, visualRadii[key]);
      shells[key] = s;
      scene.add(s.group);
      attachTrajectoryCone(THREE, s);
    }

    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();

    clock = new THREE.Clock();
    bindCameraControls(canvas);
    animate();
    window.addEventListener("resize", resize);
    // Watch canvas size changes (CSS-driven, e.g. when rail widths or tabs change)
    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(resize);
      ro.observe(canvas);
    }
    // One more resize after a tick to account for fonts/layout settling
    requestAnimationFrame(() => requestAnimationFrame(resize));
  }

  function resize() {
    if (!renderer) return;
    const canvas = renderer.domElement;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false);
    if (camera) {
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
  }

  function makeStars(THREE, count) {
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      // Random point on large sphere
      const r = 60 + Math.random() * 40;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[3 * i + 0] = r * Math.sin(phi) * Math.cos(theta);
      positions[3 * i + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[3 * i + 2] = r * Math.cos(phi);
      sizes[i] = 0.06 + Math.random() * 0.18;
    }
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("size", new THREE.BufferAttribute(sizes, 1));

    const mat = new THREE.ShaderMaterial({
      uniforms: { color: { value: new THREE.Color(0xd6deeb) } },
      vertexShader: `
        attribute float size;
        void main() {
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * (300.0 / -mv.z);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform vec3 color;
        void main() {
          vec2 c = gl_PointCoord - 0.5;
          float d = length(c);
          if (d > 0.5) discard;
          float a = smoothstep(0.5, 0.0, d);
          gl_FragColor = vec4(color, a);
        }`,
      transparent: true,
      depthWrite: false,
    });

    return new THREE.Points(geo, mat);
  }

  function makeEarth(THREE) {
    const group = new THREE.Group();

    // Base sphere — dark navy with subtle continent-like noise
    const sphereGeo = new THREE.SphereGeometry(1, 96, 64);
    const sphereMat = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        baseColor: { value: new THREE.Color(0x0a1a36) },
        landColor: { value: new THREE.Color(0x1a3a5c) },
        glowColor: { value: new THREE.Color(0x6fd2ff) },
        lightDir: { value: new THREE.Vector3(0.6, 0.4, 0.7).normalize() },
      },
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vPos;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          vPos = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: `
        uniform vec3 baseColor;
        uniform vec3 landColor;
        uniform vec3 glowColor;
        uniform vec3 lightDir;
        varying vec3 vNormal;
        varying vec3 vPos;

        // Hash-based pseudo-noise to fake continents
        float hash(vec3 p) {
          p = fract(p * vec3(443.897, 441.423, 437.195));
          p += dot(p, p.yzx + 19.19);
          return fract((p.x + p.y) * p.z);
        }
        float noise(vec3 p) {
          vec3 i = floor(p);
          vec3 f = fract(p);
          f = f*f*(3.0-2.0*f);
          float n000 = hash(i);
          float n100 = hash(i + vec3(1,0,0));
          float n010 = hash(i + vec3(0,1,0));
          float n110 = hash(i + vec3(1,1,0));
          float n001 = hash(i + vec3(0,0,1));
          float n101 = hash(i + vec3(1,0,1));
          float n011 = hash(i + vec3(0,1,1));
          float n111 = hash(i + vec3(1,1,1));
          return mix(
            mix(mix(n000,n100,f.x), mix(n010,n110,f.x), f.y),
            mix(mix(n001,n101,f.x), mix(n011,n111,f.x), f.y),
            f.z);
        }
        float fbm(vec3 p) {
          float v = 0.0;
          float a = 0.5;
          for (int i = 0; i < 5; i++) {
            v += a * noise(p);
            p *= 2.04;
            a *= 0.5;
          }
          return v;
        }

        void main() {
          float n = fbm(vPos * 2.2);
          float land = smoothstep(0.5, 0.62, n);
          vec3 surface = mix(baseColor, landColor, land);

          // Lambert
          float diff = max(dot(vNormal, lightDir), 0.0);
          vec3 lit = surface * (0.18 + 0.95 * diff);

          // Rim glow
          float rim = 1.0 - max(dot(vNormal, vec3(0,0,1)), 0.0);
          rim = pow(rim, 2.2);
          lit += glowColor * rim * 0.25;

          gl_FragColor = vec4(lit, 1.0);
        }`,
    });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);
    group.add(sphere);

    // Wireframe overlay (latitude/longitude lines)
    const wireGeo = new THREE.SphereGeometry(1.002, 24, 16);
    const wireMat = new THREE.LineBasicMaterial({
      color: 0x4a6890,
      transparent: true,
      opacity: 0.18,
    });
    const wire = new THREE.LineSegments(new THREE.WireframeGeometry(wireGeo), wireMat);
    group.add(wire);

    group.userData.sphere = sphere;
    group.userData.wire = wire;
    return group;
  }

  function makeAtmosphere(THREE) {
    const geo = new THREE.SphereGeometry(1.08, 64, 48);
    const mat = new THREE.ShaderMaterial({
      uniforms: { glowColor: { value: new THREE.Color(0x6fd2ff) } },
      vertexShader: `
        varying vec3 vNormal;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: `
        uniform vec3 glowColor;
        varying vec3 vNormal;
        void main() {
          float intensity = pow(0.85 - dot(vNormal, vec3(0.0,0.0,1.0)), 2.6);
          gl_FragColor = vec4(glowColor, intensity * 0.9);
        }`,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      transparent: true,
      depthWrite: false,
    });
    return new THREE.Mesh(geo, mat);
  }

  function makeShell(THREE, radius) {
    const group = new THREE.Group();

    // Translucent sphere (the shell itself)
    const shellGeo = new THREE.SphereGeometry(radius, 64, 48);
    const shellMat = new THREE.MeshBasicMaterial({
      color: 0x3fd6a3,
      transparent: true,
      opacity: 0.04,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const sphere = new THREE.Mesh(shellGeo, shellMat);
    group.add(sphere);

    // Wireframe outline (subtle)
    const wireMat = new THREE.LineBasicMaterial({
      color: 0x3fd6a3,
      transparent: true,
      opacity: 0.18,
    });
    const wire = new THREE.LineSegments(
      new THREE.WireframeGeometry(new THREE.SphereGeometry(radius, 28, 14)),
      wireMat
    );
    group.add(wire);

    // Equatorial ring + tilted ring — visual hint of orbital plane
    const ringGeo = new THREE.TorusGeometry(radius, 0.005, 8, 96);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x3fd6a3,
      transparent: true,
      opacity: 0.45,
    });
    const ring1 = new THREE.Mesh(ringGeo, ringMat);
    ring1.rotation.x = Math.PI / 2;
    group.add(ring1);
    const ring2 = new THREE.Mesh(ringGeo, ringMat.clone());
    ring2.rotation.x = Math.PI / 2;
    ring2.rotation.y = Math.PI / 3;
    group.add(ring2);

    // Instanced satellites (active hardware)
    const satGeo = new THREE.SphereGeometry(0.012, 6, 6);
    const satMat = new THREE.MeshBasicMaterial({ color: 0x6fd2ff });
    const sats = new THREE.InstancedMesh(satGeo, satMat, SAT_CAP);
    sats.count = 0;
    group.add(sats);

    // Glow halo for satellites — bigger transparent point sprite
    const haloGeo = new THREE.SphereGeometry(0.022, 6, 6);
    const haloMat = new THREE.MeshBasicMaterial({
      color: 0x6fd2ff,
      transparent: true,
      opacity: 0.18,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const halos = new THREE.InstancedMesh(haloGeo, haloMat, SAT_CAP);
    halos.count = 0;
    group.add(halos);

    // Instanced debris
    const debGeo = new THREE.SphereGeometry(0.007, 4, 4);
    const debMat = new THREE.MeshBasicMaterial({ color: 0xc790ff });
    const debris = new THREE.InstancedMesh(debGeo, debMat, DEB_CAP);
    debris.count = 0;
    group.add(debris);

    // Pre-generate orbital params for each potential instance
    const sat_axes = [], sat_speeds = [], sat_phases = [];
    for (let i = 0; i < SAT_CAP; i++) {
      sat_axes.push(randomAxis(THREE));
      sat_speeds.push(0.06 + Math.random() * 0.08); // rad/s
      sat_phases.push(Math.random() * Math.PI * 2);
    }
    const deb_axes = [], deb_speeds = [], deb_phases = [];
    for (let i = 0; i < DEB_CAP; i++) {
      deb_axes.push(randomAxis(THREE));
      deb_speeds.push(0.04 + Math.random() * 0.12);
      deb_phases.push(Math.random() * Math.PI * 2);
    }

    return {
      group,
      sphere,
      wire,
      ring1,
      ring2,
      sats,
      halos,
      debris,
      cone: null, // set by attachTrajectoryCone below
      coneMat: null,
      radius,
      sat_axes,
      sat_speeds,
      sat_phases,
      deb_axes,
      deb_speeds,
      deb_phases,
      _mats: { shellMat, wireMat, ringMat, satMat, haloMat, debMat },
    };
  }

  function attachTrajectoryCone(THREE, shell) {
    // Cone from Earth's surface outward toward the shell — visualises the
    // launch corridor + L_fold pressure. Opacity scales with L/L_fold.
    const r = shell.radius;
    const coneHeight = r - 1.0; // from surface (1.0) to shell radius
    const geo = new THREE.ConeGeometry(0.35, coneHeight, 32, 1, true);
    // Default cone points +Y; we want apex at Earth's surface, base outward.
    // Move geo so apex sits at origin and base is at +Y = coneHeight.
    geo.translate(0, coneHeight / 2, 0);
    const mat = new THREE.ShaderMaterial({
      uniforms: {
        color: { value: new THREE.Color(0x3fd6a3) },
        intensity: { value: 0.0 },
      },
      vertexShader: `
        varying float vY;
        varying vec3 vNormal;
        void main() {
          vY = position.y;
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: `
        uniform vec3 color;
        uniform float intensity;
        varying float vY;
        varying vec3 vNormal;
        void main() {
          float t = clamp(vY, 0.0, 1.0);
          float alpha = (1.0 - t * 0.7) * intensity * 0.35;
          // Rim falloff so cone fades on edges
          float rim = 1.0 - abs(dot(vNormal, vec3(0,0,1)));
          alpha *= 0.4 + 0.6 * rim;
          gl_FragColor = vec4(color, alpha);
        }`,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const cone = new THREE.Mesh(geo, mat);
    cone.visible = false;
    shell.group.add(cone);
    shell.cone = cone;
    shell.coneMat = mat;
    return cone;
  }

  function randomAxis(THREE) {
    // Random unit vector with a bias toward Z axis (so orbits stay readable)
    const v = new THREE.Vector3(
      (Math.random() - 0.5) * 2,
      (Math.random() - 0.5) * 2,
      (Math.random() - 0.5) * 2
    );
    return v.normalize();
  }

  // Status -> color
  const STATUS_COLORS = {
    safe:    { hex: 0x3fd6a3, css: "#3fd6a3" },
    caution: { hex: 0xffb547, css: "#ffb547" },
    danger:  { hex: 0xff5a76, css: "#ff5a76" },
  };

  function setShellStatus(key, status) {
    const s = shells[key];
    if (!s) return;
    const col = STATUS_COLORS[status] || STATUS_COLORS.safe;
    s._mats.shellMat.color.setHex(col.hex);
    s._mats.wireMat.color.setHex(col.hex);
    s._mats.ringMat.color.setHex(col.hex);
    s._mats.shellMat.opacity = status === "danger" ? 0.07 : 0.04;
    s._mats.wireMat.opacity = status === "danger" ? 0.28 : 0.18;
  }

  function setShellPopulation(key, S, D) {
    const s = shells[key];
    if (!s) return;
    // Scale real S, D down to instance cap (preserve relative ratios across shells)
    const sCount = Math.min(SAT_CAP, Math.max(0, Math.round(S / 12)));
    const dCount = Math.min(DEB_CAP, Math.max(0, Math.round(D / 12)));
    s.sats.count = sCount;
    s.halos.count = sCount;
    s.debris.count = dCount;
  }

  function setVisibility({ showSats, showDebris, showShellSurface, showWireframe }) {
    for (const key of SHELL_KEYS) {
      const s = shells[key];
      if (!s) continue;
      s.sats.visible = showSats;
      s.halos.visible = showSats;
      s.debris.visible = showDebris;
      s.sphere.visible = showShellSurface;
      s.wire.visible = showWireframe;
    }
  }

  function setEarthStyle(style) {
    if (!earth) return;
    const sphere = earth.userData.sphere;
    const wire = earth.userData.wire;
    if (style === "wireframe") {
      sphere.visible = false;
      wire.material.opacity = 0.6;
    } else if (style === "minimal") {
      sphere.visible = true;
      wire.material.opacity = 0.08;
    } else {
      sphere.visible = true;
      wire.material.opacity = 0.18;
    }
  }

  function setAltitudeExaggeration(factor) {
    // factor in [0.6, 2.0]: 1.0 = default
    const base = { A: 1.42, B: 1.66, C: 1.92 };
    for (const key of SHELL_KEYS) {
      const r = 1 + (base[key] - 1) * factor;
      const s = shells[key];
      if (!s) continue;
      s.radius = r;
      // Rescale the shell group
      s.group.scale.setScalar(r / s.sphere.geometry.parameters.radius);
    }
  }

  function setAutoRotate(v) { autoRotate = v; }

  function setShellClickHandler(fn) { shellClickHandler = fn; }

  function focusOnShell(key) {
    const s = shells[key];
    if (!s) return;
    // 2.82 = 4.0 / visualRadii.A — chosen so Shell A (r≈1.42) zooms to ~4.0,
    // which the user confirmed looks right. B and C scale proportionally.
    cameraTargetDist = s.radius * 2.82;
    autoRotate = false;
  }

  // ── Annular zone picking ──────────────────────────────────────────────────
  // Zones from inside-out: within Shell A's silhouette → A, A..B → B, B..C → C
  function getShellAtScreen(clientX, clientY, canvas) {
    const THREE = window.THREE;
    const rect = canvas.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;
    // Project Earth centre (0,0,0) to screen pixels
    const c = new THREE.Vector3(0, 0, 0).project(camera);
    const cx = (c.x * 0.5 + 0.5) * rect.width;
    const cy = (1 - (c.y * 0.5 + 0.5)) * rect.height;
    const dist = Math.sqrt((mx - cx) ** 2 + (my - cy) ** 2);
    // True silhouette radius of a sphere of radius r at camera distance d:
    //   screenR = (halfH / tan(fov/2)) * r / sqrt(d² - r²)
    const d = camera.position.length();
    const halfH = rect.height / 2;
    const fovRad = camera.fov * Math.PI / 180;
    const focal = halfH / Math.tan(fovRad / 2);
    for (const key of SHELL_KEYS) {          // A first (innermost)
      const s = shells[key];
      if (!s) continue;
      const r = s.radius;
      const screenR = focal * r / Math.sqrt(Math.max(0.0001, d * d - r * r));
      if (dist <= screenR) return key;
    }
    return null;
  }

  function setHoverHighlight(key) {
    for (const k of SHELL_KEYS) {
      const s = shells[k];
      if (!s) continue;
      const on = k === key;
      s._mats.shellMat.opacity = on ? 0.12 : 0.04;
      s._mats.wireMat.opacity  = on ? 0.55 : 0.18;
      s._mats.ringMat.opacity  = on ? 0.85 : 0.45;
      if (s.ring2) s.ring2.material.opacity = on ? 0.85 : 0.45;
    }
    hoveredShellKey = key;
  }

  function setShellHoverHandler(fn) { shellHoverHandler = fn; }

  function resetView() {
    cameraTargetDist = 5.4;
    cameraTargetYaw = 0.4;
    cameraTargetPitch = 0.2;
  }

  function setTrajectoryIntensity(key, intensity) {
    // intensity: 0..1+ — usually L_fraction. Cone fades in past 0.5.
    const s = shells[key];
    if (!s || !s.cone || !s.coneMat) return;
    const t = Math.max(0, Math.min(1.2, intensity));
    const shown = t > 0.3;
    s.cone.visible = shown;
    s.coneMat.uniforms.intensity.value = Math.max(0, (t - 0.3) / 0.7);
    // Color also reflects state
    const col = t >= 0.95 ? 0xff5a76 : t >= 0.8 ? 0xffb547 : 0x3fd6a3;
    s.coneMat.uniforms.color.value.setHex(col);
  }

  function bindCameraControls(canvas) {
    let dragging = false;
    let downX = 0, downY = 0;
    let lastX = 0, lastY = 0;
    let movedDistance = 0;

    canvas.addEventListener("pointerdown", (e) => {
      dragging = true;
      downX = lastX = e.clientX;
      downY = lastY = e.clientY;
      movedDistance = 0;
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener("pointerup", (e) => {
      const wasClick = dragging && movedDistance < 5;
      dragging = false;
      canvas.releasePointerCapture(e.pointerId);
      if (wasClick && shellClickHandler) {
        handleSceneClick(canvas, e.clientX, e.clientY);
      }
    });
    canvas.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      movedDistance += Math.abs(dx) + Math.abs(dy);
      if (movedDistance > 5) {
        cameraTargetYaw -= dx * 0.005;
        cameraTargetPitch -= dy * 0.005;
        cameraTargetPitch = Math.max(-1.3, Math.min(1.3, cameraTargetPitch));
        // When user drags, snap current to target (no lerp during active drag)
        cameraYaw = cameraTargetYaw;
        cameraPitch = cameraTargetPitch;
      }
      lastX = e.clientX;
      lastY = e.clientY;
    });
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      cameraTargetDist = Math.max(1.6, Math.min(10, cameraTargetDist + e.deltaY * 0.003));
    }, { passive: false });

    canvas.addEventListener("mousemove", (e) => {
      if (dragging) return;
      const key = getShellAtScreen(e.clientX, e.clientY, canvas);
      if (key !== hoveredShellKey) {
        setHoverHighlight(key);
        canvas.style.cursor = key ? "pointer" : "default";
        if (shellHoverHandler) shellHoverHandler(key);
      }
    });
    canvas.addEventListener("mouseleave", () => {
      if (hoveredShellKey !== null) {
        setHoverHighlight(null);
        canvas.style.cursor = "default";
        if (shellHoverHandler) shellHoverHandler(null);
      }
    });
  }

  function handleSceneClick(canvas, clientX, clientY) {
    // Use same annular zone logic as hover so click and hover are always consistent
    const key = getShellAtScreen(clientX, clientY, canvas);
    if (key && shellClickHandler) shellClickHandler(key);
  }

  function animate() {
    requestAnimationFrame(animate);
    const dt = clock.getDelta();
    const t = clock.elapsedTime;

    // Smooth camera lerp toward targets
    cameraDist += (cameraTargetDist - cameraDist) * 0.08;
    cameraYaw += (cameraTargetYaw - cameraYaw) * 0.08;
    cameraPitch += (cameraTargetPitch - cameraPitch) * 0.08;

    if (autoRotate) {
      cameraTargetYaw += 0.04 * dt;
      cameraYaw = cameraTargetYaw; // skip lerp while auto-rotating
    }

    // Update camera
    const cy = Math.cos(cameraYaw), sy = Math.sin(cameraYaw);
    const cp = Math.cos(cameraPitch), sp = Math.sin(cameraPitch);
    camera.position.set(
      cameraDist * cp * sy,
      cameraDist * sp,
      cameraDist * cp * cy
    );
    camera.lookAt(0, 0, 0);

    // Earth spin
    if (earth) earth.rotation.y += 0.04 * dt;
    if (atmosphere) atmosphere.rotation.y += 0.02 * dt;

    // Update satellite + debris instance positions
    const dummy = new window.THREE.Matrix4();
    const v = new window.THREE.Vector3();
    const q = new window.THREE.Quaternion();

    for (const key of SHELL_KEYS) {
      const s = shells[key];
      if (!s) continue;
      const r = 1; // group is scaled separately
      // Satellites
      for (let i = 0; i < s.sats.count; i++) {
        const axis = s.sat_axes[i];
        const angle = s.sat_phases[i] + t * s.sat_speeds[i];
        // Build position: rotate (r,0,0) around axis by angle (approx — actual is rotate (1,0,0))
        // To keep distinct orbits, treat each satellite's reference point as the axis-perpendicular plane.
        // Build using quaternion from axis-angle and a per-sat reference vector (use phase shift).
        const ref = perpVector(axis, i * 0.13);
        q.setFromAxisAngle(axis, angle);
        v.copy(ref).applyQuaternion(q).multiplyScalar(r);
        dummy.makeTranslation(v.x, v.y, v.z);
        s.sats.setMatrixAt(i, dummy);
        s.halos.setMatrixAt(i, dummy);
      }
      s.sats.instanceMatrix.needsUpdate = true;
      s.halos.instanceMatrix.needsUpdate = true;
      // Debris
      for (let i = 0; i < s.debris.count; i++) {
        const axis = s.deb_axes[i];
        const angle = s.deb_phases[i] + t * s.deb_speeds[i];
        const ref = perpVector(axis, i * 0.21);
        q.setFromAxisAngle(axis, angle);
        v.copy(ref).applyQuaternion(q).multiplyScalar(r);
        dummy.makeTranslation(v.x, v.y, v.z);
        s.debris.setMatrixAt(i, dummy);
      }
      s.debris.instanceMatrix.needsUpdate = true;
    }

    // Twinkle stars slightly
    if (starfield) starfield.rotation.y += 0.002 * dt;

    renderer.render(scene, camera);
  }

  // Construct a unit vector perpendicular to `axis`, parameterized by phase.
  // Used to pick a per-instance starting reference for the orbital position.
  const _tmpA = (typeof window !== "undefined" && window.THREE) ? new window.THREE.Vector3() : null;
  function perpVector(axis, phase) {
    const THREE = window.THREE;
    // Choose a fallback ortho vector
    const ortho = Math.abs(axis.x) < 0.9
      ? new THREE.Vector3(1, 0, 0)
      : new THREE.Vector3(0, 1, 0);
    const e1 = new THREE.Vector3().crossVectors(axis, ortho).normalize();
    const e2 = new THREE.Vector3().crossVectors(axis, e1).normalize();
    return new THREE.Vector3()
      .addScaledVector(e1, Math.cos(phase))
      .addScaledVector(e2, Math.sin(phase));
  }

  window.OrbitalScene = {
    init,
    setShellStatus,
    setShellPopulation,
    setVisibility,
    setEarthStyle,
    setAltitudeExaggeration,
    setAutoRotate,
    setShellClickHandler,
    setShellHoverHandler,
    focusOnShell,
    resetView,
    setTrajectoryIntensity,
  };
})();
