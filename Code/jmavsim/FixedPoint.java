package me.drton.jmavsim;

/**
 * Invisible fixed point, used as the look-at anchor of the escort camera.
 * showGui=false -> no BranchGroup, will not be rendered, only provides a world-coordinate anchor point.
 */
public class FixedPoint extends KinematicObject {
    public FixedPoint(World world) {
        super(world, false);
    }

    @Override
    public void update(long t, boolean paused) {
        // static anchor
    }
}
