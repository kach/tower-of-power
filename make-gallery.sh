for src in $(ls examples); do
    echo "Building $src..."
    python tower-of-power.py "examples/$src" > "gallery/$src.svg";
    echo "...done!"
done
