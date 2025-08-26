import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ---- Canvas ----
fig, ax = plt.subplots(figsize=(10, 12))
ax.set_xlim(-5.5, 5.5)
ax.set_ylim(-1.2, 12.2)
ax.axis("off")

# ---- Ground line ----
ax.plot([-5.2, 5.2], [0, 0], lw=1)

# ---- Trunk (Biology: gradients/flows) ----
trunk = mpatches.Rectangle((-0.5, 0), 1, 5, facecolor="#8B5A2B", edgecolor="none")
ax.add_patch(trunk)
ax.text(0, 2.5, "Biology (Energy Gradients, Flows)",
        ha="center", va="center", fontsize=12, fontweight="bold", color="#5a3a1a")

# ---- Roots (Physics: first principles) ----
roots = ["Photos", "Electrons", "Bonds", "Molecules", "Storage"]
root_xs = np.linspace(-4, 4, len(roots))
for x, label in zip(root_xs, roots):
    ax.plot([0, x], [0, -0.6], lw=2, color="#5a3a1a")
    ax.text(x, -0.8, label, ha="center", va="top", fontsize=10, color="#8B0000")
ax.text(0, -1.05, "Physics (Unattainable Zero → First Principles)",
        ha="center", va="center", fontsize=11, fontweight="bold")

# ---- Branches (Sociology: collisions/metamorphoses) ----
branches = [
    ("Camus\n(Plant / Absurd)", -4),
    ("Marx\n(Animal / Labor)", -2),
    ("Nietzsche\n(Man → Übermensch)", 0),
    ("Pyromancer\n(Enterprise / DI)", 2),
    ("Orwell\n(System / Platform)", 4)
]
branch_y = 6.0
for label, x in branches:
    ax.plot([0, x], [5, branch_y], color="#5a3a1a", lw=2)
    ax.text(x, branch_y+0.25, label, ha="center", fontsize=8.5, color="#0b3d91",
            rotation=15 if x > 0 else -15)

# Metamorphosis arrow across branch tips
ax.annotate("", xy=(3.6, branch_y+0.9), xytext=(-3.6, branch_y+0.9),
            arrowprops=dict(arrowstyle="<|-|>", lw=1.5))
ax.text(0, branch_y+1.2, "Ontological Metamorphoses (collisions reveal new modes of being)",
        ha="center", va="bottom", fontsize=9)

# ---- Leaves/Canopy (Neuron Pentad: emergence/epistemology) ----
leaves = ["Tactical (Faith)", "Informational (Despair)",
          "Strategic (Ideology)", "Operational (Soma+Axon)",
          "Existential (Efferents)"]
leaf_y = 8.0
for x, label in zip(root_xs, leaves):
    ax.add_patch(mpatches.Circle((x, leaf_y), 0.85, facecolor="#2e8b57", alpha=0.8, edgecolor="none"))
    ax.text(x, leaf_y, label, ha="center", va="center", fontsize=8, color="white", wrap=True)
ax.text(0, 9.1, "Emergence (Neuron Pentad)",
        ha="center", va="center", fontsize=11, fontweight="bold", color="#1b5e20")

# ---- Fruits (Posteriori: recursion/coordination/memory) ----
fruits = ["Random, e", "Order, y", "Hazard, h(t)", "Survival, S(t)", "Memory, m(t)"]
fruit_y = 10.7
for x, label in zip(root_xs, fruits):
    ax.add_patch(mpatches.Circle((x, fruit_y), 0.55, facecolor="#DAA520", alpha=0.95, edgecolor="none"))
    ax.text(x, fruit_y, label, ha="center", va="center", fontsize=8, color="black")
ax.text(0, 11.7, "Posteriori → Coordination (Surviving to Tell Tales)",
        ha="center", va="center", fontsize=11, fontweight="bold", color="#1b5e20")

# ---- Recursion loop: storage to roots ----
storage_x = root_xs[-1]  # last root is "Storage"
ax.annotate("Storage → Silicon → Gigabytes → Next Iteration",
            xy=(storage_x, -0.75), xytext=(storage_x, 10.1),
            textcoords="data",
            arrowprops=dict(arrowstyle="->", lw=1.5),
            ha="center", va="center", fontsize=9)

# ---- PBSMC strip on right ----
pbs_y = [0.2, 2.5, 6.0, 8.0, 10.7]
pbs_labels = ["P: Physics (roots)",
              "B: Biology (trunk)",
              "S: Sociology (branches)",
              "M: Metaphysics/Emergence (canopy)",
              "C: Computation/Coordination (fruits)"]
for y, lbl in zip(pbs_y, pbs_labels):
    ax.text(5.2, y, lbl, ha="left", va="center", fontsize=9)

plt.title("Tree of Knowledge — From First Principles to Recursion", fontsize=15, fontweight="bold", pad=14)

# Save
plt.savefig("./storage.jpg", dpi=300, bbox_inches="tight")
plt.close()
